import os
import sys
import time
import re

import matplotlib.pyplot as plt
from keras.preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer
from keras.utils import to_categorical

import parameters

match_newline_pattern = re.compile('\n+')


def get_matrix_memory_size(matrix):
    """
    calculate memory size of a matrix.
    :param matrix: 2d numpy array
    :return: object_size(in GB), values_size(in GB), item_size(in byte)
    """
    object_size = byte_to_gb(sys.getsizeof(matrix))
    values_size = byte_to_gb(matrix.nbytes)
    item_size = matrix.itemsize
    return object_size, values_size, item_size


def get_array_memory_size(array_shape, item_size):
    """
    calculate memory size of array using shape and item size
    :param array_shape: shape attribute of numpy array
    :param item_size: element size of array in byte
    :return: array memory size in GB
    """
    element_number = 1
    for tmp in array_shape:
        element_number *= tmp
    return byte_to_gb(element_number * item_size)


def byte_to_gb(byte_number):
    """
    convert byte to GB
    :param byte_number: byte number
    :return: GB
    """
    return byte_number / (1024 ** 3)


def get_filenames_under_path(path):
    """
    get filename seq under path.
    :param path: string
    :return: filename seq
    """
    filenames = list()
    for filename in os.listdir(path):
        filename = os.path.join(path, filename)
        if os.path.isdir(filename):
            continue
        filenames.append(filename)
    return filenames


def fit_tokenizer(path):
    """
    使用语料fit tokenizer
    :param path: corpus path
    :return: tokenizer fitted by corpus
    """
    # 不过滤标点符号，不过滤低频词
    tokenizer = Tokenizer(filters='')
    tokenizer.fit_on_texts(generate_text_from_corpus(path))
    return tokenizer


def process_format_to_model_input(input_output_pairs, vocab_size, max_length):
    """
    处理输入输出对的格式，使得符合模型的输入要求
    :param input_output_pairs: [[12, 25], [12, 25, 11], ..., [12, 25, 11, ..., 23]]
    :param vocab_size: 语料库词汇表的规模
    :param max_length: 语料库按停顿符切成序列后，最长序列（分词之后）的长度
    :return: (X, y), X: 2d numpy array, y shape: (input_output_pairs length, vocab_size+1)
    """
    y_shape = len(input_output_pairs), vocab_size + 1
    y_memory_size = get_array_memory_size(y_shape, item_size=8)
    # print('One-hot编码后的输出占用内存大小为：', y_memory_size, 'GB')
    if y_memory_size > parameters.Y_MEMORY_SIZE_THRESHOLD_GB:
        print('内存占用超过', parameters.Y_MEMORY_SIZE_THRESHOLD_GB, 'GB')
        sys.exit(0)

    # pad input sequences
    # lists of list => 2d numpy array
    input_output_pairs = pad_sequences(input_output_pairs, maxlen=max_length,
                                       padding='pre', truncating='pre')
    # print('Input-output pairs:\n', input_output_pairs)

    # split into input and output
    X, y = input_output_pairs[:, :-1], input_output_pairs[:, -1]
    # sequence prediction is a problem of multi-class classification
    # one-hot encode output, word index => one-hot vector
    y = to_categorical(y, num_classes=vocab_size + 1)
    # print((X, y))
    return X, y


def generate_text_from_corpus(path):
    """
    生成器函数，一次返回一个文本的全部内容
    :param path: corpus path
    :return: 返回迭代器，可以遍历path下所有文件的内容
    """
    filenames = get_filenames_under_path(path)
    for filename in filenames:
        with open(filename, 'r', encoding=parameters.OPEN_FILE_ENCODING) as file:
            yield file.read()


def generate_input_output_pair_from_corpus(path, tokenizer):
    """
    生成器函数，一次生成一个输入输出对
    :param path: corpus path
    :param tokenizer:
    :return: 返回一个迭代器，可以遍历由corpus生成的input-output pair的集合
    """
    for text in generate_text_from_corpus(path):
        for line in match_newline_pattern.split(text):
            # print(line)
            if line == '':
                continue
            encoded = tokenizer.texts_to_sequences([line])[0]
            # print(encoded)
            for i in range(1, len(encoded)):
                input_output_pair = encoded[: i + 1]
                # print(input_output_pair)
                yield input_output_pair


def generate_batch_samples_from_corpus(path, tokenizer, vocab_size, max_length):
    """
    生成器函数，一次生成一个批的数据
    会在数据集上无限循环
    :param path: corpus path
    :param tokenizer:
    :param vocab_size:
    :param max_length:
    :return: 返回迭代器，可以遍历由corpus生成的batch data的集合。batch data即一个批的输入矩阵和输出矩阵(X, y)
    """
    while True:
        batch_samples_count = 0
        input_output_pairs = list()
        for input_output_pair in generate_input_output_pair_from_corpus(path, tokenizer):
            # 每次生成一个批的数据，每次返回固定相同数目的样本
            if batch_samples_count < parameters.BATCH_SAMPLES_NUMBER - 1:
                input_output_pairs.append(input_output_pair)
                batch_samples_count += 1
            else:
                input_output_pairs.append(input_output_pair)
                X, y = process_format_to_model_input(input_output_pairs, vocab_size, max_length)
                yield X, y
                input_output_pairs = list()
                batch_samples_count = 0


def plot_figure(figure_name, *args):
    """
    画图，目前最多画四条曲线，传入一个(x, y)元组，就画一条曲线
    这是一个阻塞函数
    :param figure_name: 图片的名字
    :param args: 变长参数，即参数数目可变
    :return: None
    """
    colors = ['r', 'b', 'g', 'y', 'k']
    styles = ['-', '--', '-.', ':']
    max_args_num = len(styles)
    length = len(args)
    if length > max_args_num:
        print('too much tuple, more than', max_args_num)
        return
    plt.figure(figure_name)
    for i in range(length):
        plt.plot(args[i][0], args[i][1], colors[i]+styles[i], lw=3)
    if not os.path.exists(parameters.FIGURE_PATH):
        os.makedirs(parameters.FIGURE_PATH)
    current_time = time.strftime('%Y-%m-%d %H_%M_%S', time.localtime(time.time()))
    save_url = os.path.join(parameters.FIGURE_PATH, 'lm_'+current_time+'.png')
    plt.savefig(save_url)
    plt.show()  # it is a blocking function


# if __name__ == '__main__':
#     for file_content in generate_text_from_corpus('E:\自然语言处理数据集\搜狐新闻数据(SogouCS)_segment'):
#         print('111')
