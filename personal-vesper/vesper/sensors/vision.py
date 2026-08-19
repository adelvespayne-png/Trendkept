"""Ambient vision — OpenCV capture, YOLO detection, throttled.

    python -m vesper.sensors.vision      # prints detections until Ctrl-C

This loop **never calls the LLM**. It writes what it sees into the world
state and stops there; whether anything happens next is the triggers'
decision. Detection runs on an interval (default every 2s), not per frame —
that one choice is the difference between a background process and a
space heater.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import List, Optional

from ..config import CONFIG, Config, setup_logging
from ..core.world_state import WorldState
from .clock import time_of_day

LOG = logging.getLogger("vesper.vision")


class VisionLoop:
    def __init__(self, state: WorldState, cfg: Config = CONFIG) -> None:
        self.state = state
        self.cfg = cfg
        self.available = False
        self._cap = None
        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._prev_gray = None

    # -- setup ------------------------------------------------------------

    def _open(self) -> bool:
        if not self.cfg.vision_enabled:
            LOG.info("vision disabled by config")
            return False
        try:
            import cv2
        except Exception as exc:
            LOG.warning("opencv not installed (%s); vision is off. "
                        "See README step 7.", exc)
            return False
        try:
            from ultralytics import YOLO
        except Exception as exc:
            LOG.warning("ultralytics not installed (%s); vision is off", exc)
            return False

        cap = cv2.VideoCapture(self.cfg.camera_index)
        if not cap.isOpened():
            LOG.warning("camera %s did not open; vision is off",
                        self.cfg.camera_index)
            cap.release()
            return False
        self._cap = cap

        try:
            # Downloads the weights on first use.
            self._model = YOLO(self.cfg.yolo_model)
        except Exception as exc:
            LOG.error("could not load %s: %s", self.cfg.yolo_model, exc)
            cap.release()
            self._cap = None
            return False

        self.available = True
        return True

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self._open():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="vision",
                                        daemon=True)
        self._thread.start()
        self.state.update(vision_active=True)
        LOG.info("watching camera %s every %.1fs",
                 self.cfg.camera_index, self.cfg.vision_interval)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap is not None:
            self._cap.release()
        self.state.update(vision_active=False)

    # -- the loop ---------------------------------------------------------

    def _loop(self) -> None:
        import cv2

        while not self._stop.is_set():
            started = time.monotonic()
            ok, frame = self._cap.read()
            if not ok:
                LOG.debug("dropped frame")
                time.sleep(self.cfg.vision_interval)
                continue

            # Motion is far cheaper than detection, and it's what the
            # "nothing has moved for 20 minutes" rules run on.
            gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                                    (21, 21), 0)
            if self._prev_gray is not None:
                delta = cv2.absdiff(self._prev_gray, gray)
                moved = int((cv2.threshold(delta, 25, 255,
                                           cv2.THRESH_BINARY)[1] > 0).sum())
                if moved > 1500:
                    self.state.touch_motion()
            self._prev_gray = gray

            try:
                labels = self._detect(frame)
            except Exception:
                LOG.exception("detection failed")
                labels = []

            people = ["unknown"] * labels.count("person")
            objects = sorted(set(labels))
            self.state.update(people=people, objects=objects,
                              time_of_day=time_of_day())

            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, self.cfg.vision_interval - elapsed))

    def _detect(self, frame) -> List[str]:
        results = self._model(frame, verbose=False,
                              conf=self.cfg.vision_confidence)
        labels: List[str] = []
        for res in results:
            names = res.names
            for box in res.boxes:
                labels.append(names[int(box.cls[0])])
        return labels



def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    state = WorldState()
    loop = VisionLoop(state)
    if not loop.start():
        print("Vision unavailable here. Set VISION_ENABLED=true, install "
              "opencv-python + ultralytics, and attach a camera.")
        return 1
    print("Watching. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(CONFIG.vision_interval)
            print(" ", state.snapshot().describe())
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
