from cog import BasePredictor, Path, Input
import torch
import subprocess
import os
import shutil
import boto3
from botocore.client import Config

class Predictor(BasePredictor):
    def setup(self):
       print("Setting up things if needed")
       # move into /Real-ESRGAN
       os.chdir('/Real-ESRGAN')
       # launch python setup.py develop
       cmd = [
        'python',
        'setup.py',
        'develop'
       ]
       process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
       stdout, stderr = process.communicate()
       if process.returncode != 0:
        print(stderr)
        raise RuntimeError(stderr)

    def predict(self, 
                video: Path = Path(description="Video", default=None),
                face_enhance: bool = Input(description="Face Enhance", default=True),
                s3_bucket: str = Input(description="S3 Bucket", default=None),
                s3_region: str = Input(description="S3 Region", default=None),
                s3_access_key: str = Input(description="S3 Access Key", default=None),
                s3_secret_key: str = Input(description="S3 Secret Key", default=None),
                s3_endpoint_url: str = Input(description="S3 Endpoint URL", default=None),
                s3_use_ssl: bool = Input(description="S3 Use SSL", default=True),
                s3_path: str = Input(description="S3 Path", default=None)
                ) -> Path:
        input_path = str(video)
        print("input_path: ", input_path)
        temp_folder = 'extracted_frames'
        enhanced_folder = 'enhanced_frames'

    

        # get fps from video
        cmd = [
            'ffprobe',
            '-v',
            'error',
            '-select_streams',
            'v',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            '-show_entries',
            'stream=r_frame_rate',
            input_path
        ]

        fps = subprocess.check_output(cmd).decode('utf-8').strip().split('/')
        fps = float(fps[0]) / float(fps[1])
        print(f"Video FPS: {fps}")

        if os.path.isdir(temp_folder):
            shutil.rmtree(temp_folder)
        os.mkdir(temp_folder)

        ####################################### Extract Frames  #######################################
        cmd = [
            'ffmpeg',
            '-i',
            input_path,
            '-r',
            str(fps),
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


        ####################################### Extract Audio #######################################

        # get audio extension
        cmd = [
            'ffprobe',
            '-v',
            'error',
            '-select_streams',
            'a',
            '-show_entries',
            'stream=codec_name',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            input_path
        ]


        audio_extension = subprocess.check_output(cmd).decode('utf-8').strip()
        print(f"Audio Extension: {audio_extension}")

        audio_path = 'audio.' + audio_extension

        # try to remove audio_path if exists
        if os.path.exists(audio_path):
            os.remove(audio_path)
            

        cmd = "ffmpeg -i " + input_path + " -vn -acodec copy " + audio_path
        os.system(cmd)

        ####################################### Process Frames #######################################
        print("Processing Frames...")
        frame_count = len(os.listdir(temp_folder))
        print(f"Enhancing {frame_count} Frames with ESRGAN...")

        if os.path.isdir(enhanced_folder):
            shutil.rmtree(enhanced_folder)
        os.mkdir(enhanced_folder)


        # for each frame in temp_folder, enhance it and save it in enhanced_folder
        currentFrame = 0    

        if face_enhance:
            cmd = [
                'python',
                'inference_realesrgan.py',
                '-n',
                'RealESRGAN_x4plus',
                '-i',
                f'{temp_folder}',
                '--outscale',
                '4',
                '--face_enhance',
                '-o',
                f'{enhanced_folder}',
            ]
        else:
            cmd = [
                'python',
                'inference_realesrgan.py',
                '-n',
                'RealESRGAN_x4plus',
                '-i',
                f'{temp_folder}',
                '--outscale',
                '4',
                '-o',
                f'{enhanced_folder}',
            ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(stderr)
            raise RuntimeError(stderr)
        else:
            print(f"Done, Enhanced {frame_count} Frames")

        ####################################### Create Video #######################################
        print("Creating Video...")

        result_folder = 'results'


        if os.path.isdir(result_folder):
            shutil.rmtree(result_folder)
        os.mkdir(result_folder)




        cmd = [
            'ffmpeg',
            '-r',
            str(fps),
            '-i',
            f'{enhanced_folder}/frame_%08d_out.png',
            '-i',
            '/Real-ESRGAN/' + audio_path,
            '-c:v',
            'libx264',
            '-pix_fmt',
            'yuv420p',
            '-crf',
            '10',
            '-c:a',
            'aac',
            '-strict',
            '-2',
            f'{result_folder}/enhanced_video.mp4'
        ]



        print('######################################### cmd : ', cmd)

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(stderr)
            raise RuntimeError(stderr)
        else:
            print("Done Recreating Video")

            ####################################### S3 Upload Video #######################################
            print("Uploading Video to S3...") 
            # use pathstyle because minio does not support virtual host style
            s3 = boto3.client(
                's3',
                region_name=s3_region,
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                endpoint_url="https://" + s3_endpoint_url,
                use_ssl=s3_use_ssl,
                config=boto3.session.Config(signature_version='s3v4'),
                verify=False
            )
            
            import datetime
            # create a timespamp for video name ex 5345446354.mp4
            timestamp = datetime.datetime.now().timestamp()

            s3.upload_file(
                Filename=f'{result_folder}/enhanced_video.mp4',
                Bucket=s3_bucket,
                Key=f'{s3_path}/{timestamp}.mp4',
            )

            print("Done Uploading Video to S3")

            # get the url of the uploaded video for 7 days
            url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': s3_bucket,
                    'Key': f'{s3_path}/{timestamp}.mp4'
                },
                ExpiresIn=604800
            )

            return url

