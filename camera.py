#
# NP AIG Assignment 1
# Camera
#

import subprocess
from pathlib import Path
from pygame import image
from abc import ABC, abstractmethod
from tempfile import mkdtemp
from shutil import rmtree


class Camera:
    """Defines an abstract camera that records frames for the game"""

    @abstractmethod
    def record(self, surface):
        """
        Record a single frame from the given Pygame surface
        """
        pass

    @abstractmethod
    def export(self, path, cleanup=True):
        """
        Export the recording as MP4 file written to the given path
        The given path should end with the '.mp4' extension.
        Optionally, cleanup recorded frames.
        Cannot export after cleaning up recorded frames.
        """
        pass


class NOPCamera(Camera):
    """Defines a do nothing camera."""

    def record(self, surface):
        pass

    def export(self, path, cleanup=True):
        pass


class FFmpegCamera(Camera):
    """
    Defines a camera that records frames an stiches them into a video with FFmpeg.
    Assumes that ffmpeg is installed on the system an accessible via the system path.
    """

    def __init__(self):
        super().__init__()
        self.frame_step = 0
        # create temporary directory to store frames
        self.frames_dir = mkdtemp(prefix="ffmpeg_frames_")

    def record(self, surface):
        # record frame by write frame as image to frame directory
        # this should record around
        frame_path = Path(self.frames_dir) / f"frame_{self.frame_step}.png"
        image.save(surface, str(frame_path))
        self.frame_step += 1

    def export(self, path, cleanup=True):
        # resolve absolute output path to pass to ffmpe.
        output_path = str(Path(path).resolve())
        print(output_path)
        print(f"ffmpeg -framerate 30 -i frame_%d.png {output_path}")
        # convert the frames into a video with FFmpeg
        encode_run = subprocess.run([
            "ffmpeg",
            "-framerate", "30",
            "-i",  "frame_%d.png",
            output_path,
        ], cwd=self.frames_dir)
        print(encode_run.stdout)
        if encode_run.returncode != 0:
            raise Exception(f"FFmpeg failed to encode video from frames: \n{encode_run.stderr}")
        # optionally clean up recorded frames
        if cleanup:
            rmtree(self.frames_dir)


cameras = {
    "NOPCamera": NOPCamera,
    "FFmpegCamera": FFmpegCamera,
}
