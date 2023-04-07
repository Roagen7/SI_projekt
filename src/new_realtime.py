import copy
import threading

import noisereduce
import pyaudio
import numpy as np
import time
import wave
import matplotlib.pyplot as plt
import pygame
from joblib import load
from scipy.io.wavfile import write
import src.data_engineering.spectrogram as sp
import sounddevice as sd

import macros


def new_realtime(modelfile, with_bg=False):
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 512
    RECORD_SECONDS = 3
    window = np.blackman(sp.CHUNK_SIZE)
    state = 'in'
    prev_state = 'in'
    model = load(f'{macros.model_path}{modelfile}.joblib')
    scaler = load(f'{macros.model_path}{modelfile}_scaler.joblib')
    avgnoise=0
    plt.ion()
    fig = plt.figure(figsize=(10, 8))
    ax1 = fig.add_subplot(211)
   # ax2 = fig.add_subplot(212)
    ax3 = fig.add_subplot(212)

    saved = []
    p = None
    stream = None
    contin = True
    saved_chunks = 50



    def record_thread():
        nonlocal stream
        nonlocal saved
        nonlocal contin
        nonlocal saved_chunks
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                        frames_per_buffer=sp.CHUNK_SIZE)
        while contin:
            waveData = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
            # sd.play(waveData, 44100)
            saved = saved + list(waveData)
            if saved.__len__() >= (saved_chunks+1)*CHUNK:
                saved = saved[CHUNK:]
        stream.stop_stream()
        stream.close()
        p.terminate()

    def write_thread():
        nonlocal saved

    def soundPlot():
        nonlocal state, prev_state, saved, window, state, prev_state, ax1, ax3, model, scaler, avgnoise
        i = 0
        k=0
        while True:
            #t1 = time.time()
            if saved.__len__() >= (saved_chunks)*CHUNK:
                data = sp.signal_clean(saved)
                npArrayData = np.array([i if i>avgnoise else 0 for i in saved[saved.__len__() - sp.CHUNK_SIZE:]])
                npArrayData_reduced = np.array([i if i>avgnoise else 0 for i in data[data.__len__() - sp.CHUNK_SIZE:]])

                t_pred = copy.deepcopy(npArrayData)
                t_pred = [i for i in t_pred]
                #t_pred = [i for i in t_pred]
                #t_pred = noisereduce.reduce_noise(t_pred, 44100)
                t_pred = np.abs(np.fft.rfft(t_pred))
                t_pred = t_pred[t_pred.__len__() - 160:]
                t_pred = np.append(t_pred, [1 if prev_state == 'in' else -1])

                indata = npArrayData * window
                fftData = np.abs(np.fft.rfft(indata))
                fftData = fftData[fftData.__len__() - 161:]
                fftTime = np.fft.rfftfreq(sp.CHUNK_SIZE, 1. / RATE)
                fftTime = fftTime[fftTime.__len__() - 161:]

                indata2 = npArrayData_reduced * window
                fftData2 = np.abs(np.fft.rfft(indata2))
                fftData2 = fftData2[fftData2.__len__() - 161:]

                scaled = scaler.transform(t_pred.reshape(-1, 1).T)
                state = model.predict(scaled)
                which = fftData[1:].argmax() + 1

                # Plot time domain
                ax1.cla()
                ax1.plot(indata, 'g' if prev_state == 'in' else 'r')
                ax1.grid()
                # ax3.cla()
                ax1.plot(indata2, 'b' if prev_state == 'in' else 'y')
                # ax3.grid()
                if np.mean(fftData) > avgnoise:
                    ax1.set_title(('in' if prev_state == 'in' else 'out') + k.__str__())
                else:
                    ax1.set_title('none')
                ax1.axis([0, sp.CHUNK_SIZE, -1000, 1000])
              #  ax3.axis([0, sp.CHUNK_SIZE, -5000, 5000])
                # Plot frequency domain graph
                # ax2.cla()
                # ax2.plot(fftTime, fftData, 'g' if prev_state == 'in' else 'r')
                # ax2.grid()
                # ax2.axis([0, 5000, 0, 10 ** 6])
                # ax3.cla()
                # ax3.plot(fftTime, fftData2, 'b' if prev_state == 'in' else 'y')
                # ax3.grid()
                # ax3.axis([0, 5000, 0, 10 ** 6])
                plt.pause(0.001)
                # print("took %.02f ms" % ((time.time() - t1) * 1000))
                # # use quadratic interpolation around the max
                # if which != len(fftData) - 1:
                #     y0, y1, y2 = np.log(fftData[which - 1:which + 2:])
                #     x1 = (y2 - y0) * .5 / (2 * y1 - y2 - y0)
                #     # find the frequency and output it
                #     thefreq = (which + x1) * RATE / CHUNK
                #     print("The freq is %f Hz." % (thefreq))
                # else:
                #     thefreq = which * RATE / CHUNK
                #     print("The freq is %f Hz." % (thefreq))

                prev_state = state
                # i += 1
                # k+=100
                # if i == 1000:
                #     break


    if with_bg:
        record_time_s = 25
        record_bg_time_s = 10
        sample_rate = 44100
        channels = 1

        pygame.init()
        pygame.font.init()
        screen = pygame.display.set_mode((740, 480))
        font = pygame.font.SysFont(None, 50)
        tr = threading.Thread(target=record_thread, args=(1000,))
        tr.start()
        t0 = time.time()

        while time.time() - t0 < record_bg_time_s:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    tr.join()
                    pygame.quit()
                    return

            screen.fill((0, 0, 0))
            text = font.render(
                f'Recording background, try not to breath: {(record_bg_time_s - time.time() + t0).__str__()}', True,
                (255, 255, 255))
            screen.blit(text, (0, 0))
            pygame.display.update()
        contin = False
        tr.join()
        pygame.quit()
        avgnoise = np.mean(saved)
        saved = []
        #sd.stop()
    contin = True

    tr = threading.Thread(target=record_thread)
    tr2 = threading.Thread(target=write_thread)
    tr.start()
    tr2.start()
    soundPlot()
    contin = False
    tr.join()
    write('test.wav', RATE, np.array(saved))
    tr2.join()
