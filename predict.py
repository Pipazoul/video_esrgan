from cog import BasePredictor, Path
import torch
import subprocess
import os
import shutil

class Predictor(BasePredictor):
    def setup(self):
       print("Setting up things if needed")

    def predict(self, video: Path = Path(description="Video", default=None)) -> Path:
        input_path = str(video)
        print("input_path: ", input_path)
        temp_folder = 'extracted_frames'

        if os.path.isdir(temp_folder):
            shutil.rmtree(temp_folder)
        os.mkdir(temp_folder)

        ####################################### Extract Frames #######################################
        cmd = [
            'ffmpeg',
            '-i',
            input_path,
            '-qscale:v',
            '1',
            '-qmin',
            '1',
            '-qmax',
            '1',
            '-vsync',
            '0',
            f'{temp_folder}/frame_%08d.png'
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(stderr)
            raise RuntimeError(stderr)
        else:
            frame_count = len(os.listdir(temp_folder))
            print(f"Done, Extracted {frame_count} Frames")

        ####################################### Process Frames #######################################
        print("Processing Frames...")

        # Add your frame processing logic here

        ####################################### Create Video #######################################
        print("Creating Video...")

        result_folder = 'results'

        if os.path.isdir(result_folder):
            shutil.rmtree(result_folder)
        os.mkdir(result_folder)

        fps = 15  # Change the frame rate as per your requirement

        print(f"Recompiling {frame_count} Frames into Video...")
        cmd = [
            'ffmpeg',
            '-i',
            f'{temp_folder}/frame_%08d.png',
            '-c:a',
            'copy',
            '-c:v',
            'libx264',
            '-r',
            str(fps),
            '-pix_fmt',
            'yuv420p',
            f'{result_folder}/enhanced_video.mp4'
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(stderr)
            raise RuntimeError(stderr)
        else:
            print("Done Recreating Video")
            return Path(f'{result_folder}/enhanced_video.mp4')
