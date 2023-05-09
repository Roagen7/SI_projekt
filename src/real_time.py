import time
import threading
import noisereduce
import numpy as np
import pygame
import pyaudio

import src.data_engineering.spectrogram as sp

from scipy.io.wavfile import write

WIN_WIDTH = 740
WIN_HEIGHT = 480
SAMPLERATE = 44100
NOISE_REDUCTION_PERIOD = 176400
BALL_POS = (WIN_WIDTH/2, WIN_HEIGHT/4)
BALL_START_RADIUS = 100
PLOT_HEIGHT = WIN_HEIGHT * 3 / 4
PLOT_MARGIN = 10

MIN_MAX_BALL = {"min": 10, "max": 150}
MIN_MAX_FVAL = {"min": -200, "max": 200}

THRESHOLD = 300


def detection(model, scaler, uses_previous_state=False, loudonly=False):
    pygame.init()
    pygame.font.init()

    screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
    p = pyaudio.PyAudio()


    samples = np.array([])
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLERATE, input=True, frames_per_buffer=1024)

    run_thread = True
    def record_thread():
        nonlocal samples
        while run_thread:
                data = np.frombuffer(stream.read(512, exception_on_overflow=False), dtype=np.int16)
                data = data / 50
                samples = np.append(samples, data)

    tr = threading.Thread(target=record_thread)
    tr.start()

    state = 'in'
    prev_state = 'in'

    radius = BALL_START_RADIUS
    fx = 0
    pred_history = []
    pred_label = []
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run_thread = False
                tr.join()
                stream.stop_stream()
                stream.close()
                p.terminate()
                write('test.wav', SAMPLERATE, samples)
                pygame.quit()
                return
        screen.fill((0, 0, 0))

        if samples.shape[0] > NOISE_REDUCTION_PERIOD:
            clean = noisereduce.reduce_noise(samples[-NOISE_REDUCTION_PERIOD:], SAMPLERATE)

            last_frame = abs(np.fft.rfft(clean[len(clean) - sp.CHUNK_SIZE:]))
            last_frame = sp.signal_clean(last_frame)

            if uses_previous_state:
                last_frame = np.append(last_frame, 1 if prev_state == 'in' else -1)

            if sum(last_frame) > THRESHOLD or not loudonly:
                last_frame_std = scaler.transform(last_frame.reshape(-1, 1).T)
                state = model.predict(last_frame_std)
                prev_state = state

            color = (0, 0, 255)
            if sum(last_frame) <= THRESHOLD:
                color = (0, 255, 0)
            elif state == "out":
                color = (255, 0, 0)
                fx -= 0.05
                radius -= 0.5
            else:
                fx += 0.1
                radius += 1

            radius = min(max(radius, MIN_MAX_BALL["min"]), MIN_MAX_BALL["max"])
            fx = min(max(fx, MIN_MAX_FVAL["min"]), MIN_MAX_FVAL["max"])

            pred_history.append(fx)
            pred_label.append(color)

            if len(pred_history) > WIN_WIDTH - 2 * PLOT_MARGIN:
                pred_history = pred_history[-(WIN_WIDTH-2 * PLOT_MARGIN):]
                pred_label = pred_label[-(WIN_WIDTH-2 * PLOT_MARGIN):]


            for x, y in enumerate(pred_history[:-1]):
                pygame.draw.line(screen, pred_label[x], (x + PLOT_MARGIN, PLOT_HEIGHT - y * 5), (x + 1 + PLOT_MARGIN, PLOT_HEIGHT - pred_history[x + 1] * 5))

            pygame.draw.circle(screen, color, BALL_POS, radius)

        pygame.display.update()
