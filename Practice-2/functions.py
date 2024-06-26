from pathlib import Path
from itertools import chain
from math import ceil
from copy import deepcopy
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
#from ccdproc import cosmicray_lacosmic
from photutils.background import Background2D
from skimage import restoration
#from image_registration import chi2_shift

def fits_list(path: Path):
    """ Создаёт итератор по всем найденным в папке файлам FITS """
    return chain.from_iterable(path.glob(f'*.{ext}') for ext in ('fts', 'fit', 'fits', 'FTS', 'FIT', 'FITS'))

def save_histogram(array: np.ndarray, path: str):
    """ Сохраняет гистограмму """
    fig, ax = plt.subplots(1, 1, figsize=(9, 6), dpi=100)
    ax.hist(array.flatten())
    fig.savefig(path)
    plt.close(fig)

def print_min_mean_max(array: np.ndarray):
    """ Печатает характеристики распределения значений в массиве """
    print(f'Min: {array.min():.2f};\tMean: {array.mean():.2f};\tMax: {array.max():.2f}.')

def array2img(array: np.ndarray):
    """ Нормализует массив по максимальному значению и сохраняет в PNG """
    mask = 1 - np.isnan(array).astype('int')
    array = np.nan_to_num(array)
    array = array.clip(0, None) / array.max()
    array = np.stack((array, mask), axis=-1)
    array *= 255
    return Image.fromarray(array.astype('uint8'), mode='LA')

def crop(array: np.ndarray, edge: bool):
    """ Инверсия вертикальной оси и обрезка чёрных краёв """
    if array.ndim == 3:
        array = array[0]
    if edge:
        return array[-22:0:-1,19:]
    else:
        return array[::-1,:]

#def cosmic_ray_subtracted(array: np.ndarray, sigma: int|float = 5):
#    """ Вычитает космические лучи """
#    return cosmicray_lacosmic(array, sigclip=sigma)[0]

def background_subtracted(array: np.ndarray, size_px: int = 200):
    """ Вычитает фон неба """
    bkg = Background2D(array, (size_px, size_px))
    return array - bkg.background

def smart_mean(cube: np.ndarray, exposures: np.ndarray, crop: bool = False):
    """ Взвешенное среднее с учётом альфа-канала """
    if crop:
        return np.average(cube, axis=0, weights=exposures)
    else:
        array = np.zeros((cube.shape[1], cube.shape[2]))
        exposure_array = np.zeros_like(array)
        for i, band in enumerate(cube):
            array += np.nan_to_num(band)
            exposure_array[~np.isnan(band)] += exposures[i]
        return array / exposure_array

def float_shift(array: np.ndarray, x_shift: float, y_shift: float):
    """ Cубпиксельный циклический сдвиг """
    array = np.nan_to_num(array)
    y_len, x_len = array.shape
    x_freq = x_shift * np.fft.fftfreq(x_len)[np.newaxis,:]
    y_freq = y_shift * np.fft.fftfreq(y_len)[:,np.newaxis]
    freq_grid = x_freq + y_freq
    kernel = np.exp(-1j*2*np.pi*freq_grid)
    return np.real(np.fft.ifftn(np.fft.fftn(array) * kernel))

def trimmed_nan(cube: np.ndarray, crop: bool):
    """ Обрезает np.nan с краёв по пространственным осям """
    if crop:
        nan_pixels = np.isnan(cube).any(axis=0)
    else:
        nan_pixels = np.isnan(cube).all(axis=0)
    return cube[:,~nan_pixels.all(axis=1),:][:,:,~nan_pixels.all(axis=0)]

# def aligned_cube(cube0: list|np.ndarray, crop: bool = False):
    # """ Выравнивание каналов спектрального куба """
    # if isinstance(cube0, list): # создание куба, если его нет
        # arrays = cube0
        # shapes = []
        # for band in arrays:
            # shapes.append(band.shape)
        # y_len0, x_len0 = np.max(shapes, axis=0)
        # bands_num = len(arrays)
        # cube0 = np.empty((bands_num, y_len0, x_len0))
        # cube0.fill(np.nan)
        # for i, band in enumerate(arrays):
            # cube0[i, :shapes[i][0], :shapes[i][1]] = band
    # else:
        # bands_num, y_len0, x_len0 = cube0.shape
    # cube0_isnan = np.isnan(cube0).astype('float')
    # green_id = ceil(bands_num / 2) - 1 # единственное неискажённое изображение будет в середине
    # shifts = [(0, 0)]
    # for i in range(bands_num-1):
        # shifts.append(chi2_shift(cube0[i], cube0[i+1], return_error=False, upsample_factor='auto'))
    # shifts = -np.array(shifts)
    # walked = np.cumsum(shifts, axis=0)
    # walked -= walked[green_id] # нормирование относительно "зелёного" изображения
    # walked_min = np.min(walked, axis=0)
    # walked_max = np.max(walked, axis=0)
    # walked_len = walked_max - walked_min
    # if crop:
        # x_len1, y_len1 = np.ceil((x_len0, y_len0) - walked_len).astype('int')
        # x_zero, y_zero = np.floor(walked_max).astype('int')
        # x_end = x_zero + x_len1
        # y_end = y_zero + y_len1
    # else:
        # x_len1, y_len1 = np.ceil((x_len0, y_len0) + walked_len).astype('int')
        # x_zero, y_zero = np.floor(-walked_min).astype('int')
        # x_end = x_zero + x_len0
        # y_end = y_zero + y_len0
    # cube1 = np.empty((bands_num, y_len1, x_len1))
    # if crop:
        # for i in range(bands_num):
            # if i == green_id:
                # cube1[i] = cube0[i, y_zero:y_end, x_zero:x_end]
            # else:
                # x_shift, y_shift = walked[i]
                # array = float_shift(cube0[i], x_shift, y_shift)
                # isnan = float_shift(cube0_isnan[i], x_shift, y_shift) > 0.5
                # array[isnan] = np.nan
                # cube1[i] = array[y_zero:y_end, x_zero:x_end]
    # else:
        # cube1.fill(np.nan)
        # for i in range(bands_num):
            # if i == green_id:
                # cube1[i, y_zero:y_end, x_zero:x_end] = cube0[i]
            # else:
                # x_shift, y_shift = walked[i]
                # array = float_shift(cube0[i], x_shift, y_shift)
                # isnan = float_shift(cube0_isnan[i], x_shift, y_shift) > 0.5
                # array[isnan] = np.nan
                # x_ceil, y_ceil = np.ceil(np.abs(walked[i])).astype('int')
                # x_floor, y_floor = np.floor(np.abs(walked[i])).astype('int')
                # if 0 not in (x_floor, y_floor):
                    # match f'{int(x_shift > 0)}, {int(y_shift > 0)}':
                        # case '1, 1':
                            # corner = deepcopy(array[:y_floor, :x_floor]) # copy
                            # array[:y_ceil, :x_ceil] = np.nan # cut
                            # cube1[i, y_end:y_end+y_floor, x_end:x_end+x_floor] = corner # paste
                        # case '1, 0':
                            # corner = deepcopy(array[-y_floor:, :x_floor]) # copy
                            # array[-y_ceil:, :x_ceil] = np.nan # cut
                            # cube1[i, y_zero-y_floor:y_zero, x_end:x_end+x_floor] = corner # paste
                        # case '0, 1':
                            # corner = deepcopy(array[:y_floor, -x_floor:]) # copy
                            # array[:y_ceil, -x_ceil:] = np.nan # cut
                            # cube1[i, y_end:y_end+y_floor, x_zero-x_floor:x_zero] = corner # paste
                        # case '0, 0':
                            # corner = deepcopy(array[-y_floor:, -x_floor:]) # copy
                            # array[-y_ceil:, -x_ceil:] = np.nan # cut
                            # cube1[i, y_zero-y_floor:y_zero, x_zero-x_floor:x_zero] = corner # paste
                # if x_floor != 0:
                    # if x_shift > 0:
                        # edge = deepcopy(array[:, :x_floor]) # copy
                        # array[:, :x_ceil] = np.nan # cut
                        # cube1[i, y_zero:y_end, x_end:x_end+x_floor] = edge # paste
                    # else:
                        # edge = deepcopy(array[:, -x_floor:]) # copy
                        # array[:, -x_ceil:] = np.nan # cut
                        # cube1[i, y_zero:y_end, x_zero-x_floor:x_zero] = edge # paste
                # if y_floor != 0:
                    # if y_shift > 0:
                        # edge = deepcopy(array[:y_floor, :]) # copy
                        # array[:y_ceil, :] = np.nan # cut
                        # cube1[i, y_end:y_end+y_floor, x_zero:x_end] = edge # paste
                    # else:
                        # edge = deepcopy(array[-y_floor:, :]) # copy
                        # array[-y_ceil:, :] = np.nan # cut
                        # cube1[i, y_zero-y_floor:y_zero, x_zero:x_end] = edge # paste
                # cube1[i, y_zero:y_end, x_zero:x_end] = array
    # return trimmed_nan(cube1, crop)

#def shifted(reference: np.ndarray, target: np.ndarray):
#    """ Определяет сдвиг и выравнивает два изображения """
#    xoff, yoff = chi2_shift(reference, target, return_error=False, upsample_factor='auto')
#    return float_shift(target, -xoff, -yoff)

def gaussian_array(width: int):
    """ Формирует ядро свёртки """
    side = np.linspace(-1, 1, width)
    x, y = np.meshgrid(side, side)
    return np.exp(-4*(x*x + y*y))

def one_div_x_array(width: int):
    """ Формирует ядро свёртки """
    side = np.linspace(-1, 1, width)
    x, y = np.meshgrid(side, side)
    return np.exp(-4*np.sqrt(x*x + y*y))

def deconvolved(array: np.ndarray, kernel: np.ndarray):
    """ Деконволюция с указанным ядром свёртки """
    return restoration.unsupervised_wiener(array, kernel, clip=False)[0]
