#
# NP AIG Assignment 1
# Camera
#

import cv2
import numpy as np
import subprocess
from pathlib import Path
from abc import ABC, abstractmethod
from tempfile import mkdtemp
from shutil import rmtree
from Globals import SCREEN_SIZE


class Camera:
    """
    Defines an abstract camera that records frames for the game
    and writes the recording to the given path
    """

    def __init__(self, path):
        self.path = path

    @abstractmethod
    def record(self, frame_str, step=0):
        """
        Record a single frame as a binary string the recorded given time step
        """
        pass

    @abstractmethod
    def export(self):
        """
        Export the recording as MP4 file
        """
        pass


class NOPCamera(Camera):
    """Defines a do nothing camera."""

    def record(self, frame_str, step=0):
        pass

    def export(self, path):
        pass


class OpenCVCamera(Camera):
    """
    Defines a camera that records frames an stiches them into a MP4 video with OpenCV.
    """

    def __init__(self, path):
        if not path.split(".")[-1].lower() == "mp4":
            raise ValueError("Only MP4 output files are supported")
        super().__init__(path)
        self.video = cv2.VideoWriter(
            path,
            cv2.VideoWriter_fourcc(*"mp4v"),
            30.0,
            SCREEN_SIZE,
        )

    def record(self, frame_str, step):
        img_rgb = np.frombuffer(frame_str, dtype=np.uint8).reshape(
            (SCREEN_SIZE[1], SCREEN_SIZE[0], 3)
        )
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        # raise Exception
        self.video.write(img_bgr)

    def export(self):
        self.video.release()


cameras = {
    "NOPCamera": NOPCamera,
    "OpenCVCamera": OpenCVCamera,
}
