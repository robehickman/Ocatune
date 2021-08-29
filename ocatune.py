import math
import array
import struct
import threading

import pygame
import pyaudio
import numpy as np


#=================================================
# Config data
#=================================================
input_device_index  = 5
output_device_index = 10

sample_format           = pyaudio.paInt16

# Input
input_samples_per_chunk = 2048
input_channels          = 2
input_sample_rate       = 48000

# Output
output_samples_per_chunk = 2048
output_channels          = 2
output_sample_rate       = 44100

# Other
referance_pitch = 440


#=================================================
# Audio utility functions
#=================================================

#---------------------------------------------------------
def sine_oscillator(frequency, sample_rate):
    increment = (2 * math.pi * frequency)/ sample_rate

    i = 0
    while True:
        res = math.sin(i) 
        i += increment
        yield res

#---------------------------------------------------------
def decode_16_bit_2ch(data):
    """
    Decode and deinterleave 16 bit 2 channel pcm audio
    """

    d = array.array('h', data)
    left  = d[0::2]
    right = d[1::2]
    return left, right


#---------------------------------------------------------
def to_16_bit(audio):
        data = bytes()

        for sample in audio:
            sample = sample * 32767
            data += struct.pack('=h', round(sample))
            data += struct.pack('=h', round(sample))

        return data


#---------------------------------------------------------
def zero_avg(waveform):
    avg = sum(waveform) / len(waveform)

    return [x - avg for x in waveform]


#---------------------------------------------------------
def scale_waveform(source, scale):
    return [scale * x for x in source]



#---------------------------------------------------------
def get_chunk_frequency(audio_chunk):
    # use a Blackman window
    window = np.blackman(input_samples_per_chunk)

    # unpack the data and times by the hamming window
    indata = np.array(audio_chunk)*window

    # Take the fft and square each value
    fftData=abs(np.fft.rfft(indata))**2

    # find the maximum
    which = fftData[1:].argmax() + 1
    # use quadratic interpolation around the max
    if which != len(fftData)-1:
        y0,y1,y2 = np.log(fftData[which-1:which+2:])
        x1 = (y2 - y0) * .5 / (2 * y1 - y2 - y0)
        # find the frequency and output it
        thefreq = (which+x1)*input_sample_rate/input_samples_per_chunk
    else:
        thefreq = which*input_sample_rate/input_samples_per_chunk

    return thefreq


#---------------------------------------------------------
def frequency_to_piano_key(frequency):
    def log2(n):
        return math.log(n, 2)

    return 12 * log2(frequency / referance_pitch ) + 49

#---------------------------------------------------------
def piano_key_to_frequency(piano_key):
    root_2_12 = 1.05946309436
    return pow(root_2_12, piano_key - 49) *  referance_pitch


#=================================================
# Audio handling
#=================================================
p                = None
input_stream     = None
output_stream    = None


shutting_down    = False
playing_thread   = None
listening_thread = None
note_to_play     = None

#---------------------------------------------------------
def note_playing_thread():
    global output_stream, note_to_play

    osc = None
    note_playing = None

    while shutting_down is False:
    # Set or clear oscillator
        if note_to_play is None:
            note_playing = None
            osc          = None

        else:
            if note_playing != note_to_play:
                note_playing = note_to_play

                freq = piano_key_to_frequency(note_to_play)
                osc = sine_oscillator(freq, output_sample_rate)

    # Audio output
        if osc is not None:
            samples = []
            for i in range(output_samples_per_chunk):
                samples.append(next(osc))

            data = to_16_bit(samples)
            output_stream.write(data)

        else:
            samples = []
            for i in range(output_samples_per_chunk):
                samples.append(0)

            data = to_16_bit(samples)
            output_stream.write(data)


#---------------------------------------------------------
def pitch_detection_thread():
    global p, input_stream, g, note_to_play

    while shutting_down is False:

    # Read microphone
        data = input_stream.read(input_samples_per_chunk, exception_on_overflow = False )
        lch, rch = decode_16_bit_2ch(data)
        audio_chunk = lch
        audio_chunk = zero_avg(audio_chunk)

        peak_amplitude = max(audio_chunk)

        if peak_amplitude > 100:
            # Detect note to play and send to audio thread
            try:
                thefreq = get_chunk_frequency(audio_chunk)

                piano_key = frequency_to_piano_key(thefreq)
                closest_piano_key = round(piano_key)

                note_to_play = round(piano_key)

            except Exception:
                pass

        else:
            note_to_play = None


#---------------------------------------------------------
def init_audio():
    global p, input_stream, output_stream, listening_thread, playing_thread

    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    #for i in range(p.get_device_count()):
    #    pprint(p.get_device_info_by_index(i))

    # =================================================
    input_stream = p.open(format             = sample_format,
                          channels           = input_channels,
                          rate               = input_sample_rate,
                          frames_per_buffer  = input_samples_per_chunk,
                          input              = True,
                          input_device_index = input_device_index
                         )

    input_stream.start_stream()

    listening_thread = threading.Thread(target=pitch_detection_thread)
    listening_thread.start()


    # =================================================
    output_stream = p.open(format              = sample_format,
                           channels            = output_channels,
                           rate                = output_sample_rate,
                           frames_per_buffer   = output_samples_per_chunk,
                           output              = True,
                           output_device_index = output_device_index
                          )

    output_stream.start_stream()

    playing_thread = threading.Thread(target=note_playing_thread)
    playing_thread.start()




#---------------------------------------------------------
def stop_audio():
    global p, input_stream, output_stream, playing_thread, shutting_down, listening_thread

    shutting_down = True

    # -----------
    listening_thread.join()
    input_stream.stop_stream()
    input_stream.close()

    # -----------
    playing_thread.join()
    output_stream.stop_stream()
    output_stream.close()

    p.terminate()




#=================================================
# Graphical interface
#=================================================
screen = None
font   = None

#---------------------------------------------------------
def init_graphics():
    global screen, font
    pygame.init()
    pygame.display.set_caption('Ocatune') 
    screen = pygame.display.set_mode([500, 500])
    pygame.font.init()
    font = pygame.font.SysFont('Arial', 30)


#---------------------------------------------------------
def graphics_loop():
    global p, input_stream, g, note_to_play

    running = True

    while running:
        # Did the user click the window close button?
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Fill the background with white
        screen.fill((255, 255, 255))

        notes_lut = {
            0  : 'A',
            1  : 'A# / Bb',
            2  : 'B',
            3  : 'C',
            4  : 'C# / Db',
            5  : 'D',
            6  : 'D# / Eb',
            7  : 'E',
            8  : 'F',
            9  : 'F# / Gb',
            10 : 'G',
            11 : 'G# / Ab'
        }

        if note_to_play is None:
            text_to_show = 'Play a note'
        else: 
            text_to_show = notes_lut[(note_to_play - 1) % 12]

        textsurface = font.render(str(text_to_show), False, (0, 0, 0))
        screen.blit(textsurface,(0,0))

        # Flip the display
        pygame.display.flip()


#---------------------------------------------------------
def stop_graphics():
    pygame.quit()

#=================================================
#=================================================

init_audio()
init_graphics()

graphics_loop()

stop_graphics()
stop_audio()

