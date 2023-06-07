FROM pytorch/pytorch:1.7.1-cuda11.0-cudnn8-runtime

RUN apt-get update && apt-get install -y gcc cmake build-essential wget ffmpeg git

WORKDIR /app
RUN git clone https://github.com/xinntao/Real-ESRGAN.git

WORKDIR /app/Real-ESRGAN

RUN pip install basicsr facexlib gfpgan
RUN pip install -r requirements.txt
RUN python setup.py develop