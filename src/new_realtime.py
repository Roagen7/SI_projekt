import copy
import sys
import time
import threading

import matplotlib.pyplot as plt
import noisereduce
import numpy as np
import pygame
import pyaudio
import sounddevice as sd
import soundcard as sc
from keras import models
from scipy.signal import savgol_filter

from TensorFlow import TensorFlow
import macros
import src.data_engineering.spectrogram as sp

from pydub import effects
from scipy.io.wavfile import write


def new_realtime():
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024
    RECORD_SECONDS = 3
    window = np.blackman(CHUNK)
    model = models.load_model(f'{macros.model_path}tensorflow')
    plt.ion()
    fig = plt.figure(figsize=(10, 8))
    ax1 = fig.add_subplot(211)

    saved = []
    p = None
    stream = None
    contin = True
    saved_chunks = 100

    pygame.init()
    pygame.font.init()

    width = 740
    height = 480
    screen = pygame.display.set_mode((width, height))
    font = pygame.font.SysFont(None, 50)
    p = pyaudio.PyAudio()
    fs = 44100

    samples = np.array([])

    stream = p.open(format=pyaudio.paInt16, channels=1, rate=fs, input=True, frames_per_buffer=1024)

    run_thread = True

    def record_thread():
        nonlocal stream
        nonlocal saved
        nonlocal contin
        nonlocal saved_chunks
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                        frames_per_buffer=CHUNK)
        while contin:
            waveData = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)

            saved.extend(waveData)
            if saved.__len__() >= (saved_chunks + 1) * CHUNK:
                sd.play(saved, 44100)
                saved = saved[CHUNK:]
        stream.stop_stream()
        stream.close()
        p.terminate()

    tr = threading.Thread(target=record_thread)
    tr.start()

    radius = 100
    tendency = 0
    while True:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run_thread = False
                tr.join()
                stream.stop_stream()
                stream.close()
                p.terminate()
                pygame.quit()
                return
        screen.fill((0, 0, 0))

        if saved.__len__() >= saved_chunks * CHUNK:
            # clean = sp.signal_clean(saved)
            commands, pred = TensorFlow.new_predict(model, saved)
            # last_frame = abs(np.fft.rfft(clean[len(clean) - sp.CHUNK_SIZE:]))
            # last_frame = sp.signal_clean(last_frame)

            color = (0, 0, 255)
            # if sum(last_frame) < 200:
            #     color = (0, 255, 0)
            if pred[1] > 0.80 and np.mean(np.abs(saved)) > 50:  # and pred[1]<10:
                tendency = tendency+1 if tendency>=0 else 0
            elif pred[0] > 0.80 and np.mean(np.abs(saved)) > 50:  # and pred[0]<10:
                tendency = tendency-1 if tendency<=0 else 0

            if tendency >= 25:
                color = (255, 0, 0)
                radius -= 1
            elif tendency <=-25:
                color = (0, 255, 0)
                radius += 1


            # for x, y in enumerate(last_frame[:-1]):
            #     pygame.draw.line(screen, color, (x*3, 480 - y), (x*3 + 3, 480 - last_frame[x+1]))

            pygame.draw.circle(screen, color, (width/2, height/2), radius)

        # if print_state == "cisza":
        #     text = font.render('cisza', True, (255, 255, 255))
        # else:
        #     text = font.render('teraz wdychasz' if state == 'in' else 'teraz wydychasz', True, (255, 255, 255))
        # screen.blit(text, (0, 0))
        pygame.display.update()


def detection_loudonly(model, scaler, chunk_size=352, input_size=40, uses_previous_state=False, with_bg=False):
    pygame.init()
    pygame.font.init()

    width = 740
    height = 480
    screen = pygame.display.set_mode((width, height))
    font = pygame.font.SysFont(None, 50)
    p = pyaudio.PyAudio()
    fs = 44100
    record_bg_time_s = 10
    channels = 1

    samples = np.array([])

    stream = p.open(format=pyaudio.paInt16, channels=1, rate=fs, input=True, frames_per_buffer=1024)

    run_thread = True
    def record_thread():
        # nonlocal stream
        nonlocal samples
        while run_thread:
                data = np.frombuffer(stream.read(512, exception_on_overflow=False), dtype=np.int16)
                data = data / 50
                samples = np.append(samples, data)

    tr = threading.Thread(target=record_thread)
    tr.start()

    state = 'in'
    prev_state = 'in'
    print_state = 'cisza'

    radius = 100
    while True:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run_thread = False
                tr.join()
                stream.stop_stream()
                stream.close()
                p.terminate()
                write('test.wav', fs, samples)
                pygame.quit()
                return
        screen.fill((0, 0, 0))

        if samples.shape[0] > chunk_size * (input_size + 200):
            clean = noisereduce.reduce_noise(samples[-176400:], 44100)

            last_frame = abs(np.fft.rfft(clean[len(clean) - sp.CHUNK_SIZE:]))
            last_frame = sp.signal_clean(last_frame)

            if sum(last_frame) < 200:
                print_state = "cisza"
            else:
                print_state = ""

            if uses_previous_state:
                last_frame = np.append(last_frame, 1 if prev_state == 'in' else -1)
                prev_state = state

            color = (0, 0, 255)
            if print_state == "cisza":
                color = (0, 255, 0)
            elif state == "out":
                color = (255, 0, 0)
                radius -= 1
            else:
                radius += 1

            # for x, y in enumerate(last_frame[:-1]):
            #     pygame.draw.line(screen, color, (x*3, 480 - y), (x*3 + 3, 480 - last_frame[x+1]))

            pygame.draw.circle(screen, color, (width/2, height/2), radius)

            last_frame_std = scaler.transform(last_frame.reshape(-1, 1).T)
            state = model.predict(last_frame_std)

        # if print_state == "cisza":
        #     text = font.render('cisza', True, (255, 255, 255))
        # else:
        #     text = font.render('teraz wdychasz' if state == 'in' else 'teraz wydychasz', True, (255, 255, 255))
        # screen.blit(text, (0, 0))
        pygame.display.update()
