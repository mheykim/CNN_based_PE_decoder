# -*- coding: utf-8 -*-
"""classifier_zeroshot_tracking.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15mDDi8VSjfED7GWZuIx8AVZQrWGR8OBd
"""
print("hi")
from scipy import signal
import scipy
import tensorflow.compat.v1 as tf
# import tensorflow.compat as tf
tf.disable_v2_behavior()
import scipy.io as sio
import numpy as np
import math
import matplotlib.pyplot as plt
from sklearn.model_selection import KFold
import os
from tqdm import tqdm
import pickle
import pdb
import mat73
from datetime import datetime
import tensorflow
#pdb.set_trace()

tf.device('/device:GPU:0')
tf.reset_default_graph()


# tf.debugging.set_log_device_placement(True)

class EarlyStopping:
    """주어진 patience 이후로 validation loss가 개선되지 않으면 학습을 조기 중지"""
    def __init__(self, label, cv, patience=2000, verbose=False, delta=0):
        """
        Args:
            patience (int): validation loss가 개선된 후 기다리는 기간
                            Default: 7
            verbose (bool): True일 경우 각 validation loss의 개선 사항 메세지 출력
                            Default: False
            delta (float): 개선되었다고 인정되는 monitered quantity의 최소 변화
                            Default: 0
        """
        self.patience = patience
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.val_loss_min = np.Inf
        # self.val_acc_max = 0  # np.Inf
        self.delta = delta
        self.label = label
        self.cv = cv

    # def __call__(self, val_acc, saver):
    def __call__(self, val_loss, saver):
        score = -val_loss
        # score = val_acc
        if self.best_score is None:
            self.best_score = score
            self.save_checkpoint(val_loss, saver)

        elif score < self.best_score + self.delta:
        # elif score < self.best_score - self.delta:
            self.counter += 1
            # print(f'EarlyStopping counter: {self.counter} out of {self.patience}')
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = score
            # self.save_checkpoint(val_acc, saver)
            self.save_checkpoint(val_loss, saver)
            self.counter = 0

    def save_checkpoint(self, val_loss, saver):
    # def save_checkpoint(self, val_acc, saver):
        '''validation loss가 감소하면 모델을 저장한다.'''

        if not os.path.exists(strings_ + '/cv{0}/label{1}/model_best'.format(self.cv, self.label)):
            os.makedirs(strings_ + '/cv{0}/label{1}/model_best'.format(self.cv, self.label))
        saver.save(sess, strings_ + '/cv{0}/label{1}/model_best'.format(self.cv, self.label) + '/dnn.ckpt')

        # if not os.path.exists(strings_ + '/cv{0}/label{1}/model_'.format(cv, lbi + 1) + str(epoch + 1)):
        #     os.makedirs(strings_ + '/cv{0}/label{1}/model_'.format(cv, lbi + 1) + str(epoch + 1))
        # saver.save(sess, strings_ + '/cv{0}/label{1}/model_'.format(cv, lbi + 1) + str(epoch + 1) + '/dnn.ckpt')

        # self.val_acc_max = val_acc

        self.val_loss_min = val_loss


def digitize_tolist(arr, bin_num=128):  # 5
    if np.unique(arr).shape == (1,):
        arr = arr+np.random.rand(*arr.shape)*1e-6
    if arr.shape[0] == 1:
        return [[bin_num/2]]
    else:
        return np.digitize(arr, np.arange(np.min(arr), np.max(arr), (np.max(arr) - np.min(arr)) / bin_num)).astype(np.uint8).tolist()


def digitize_tolist_(arr, bin_num=128):  # 5
    asdf = np.digitize(arr, np.arange(-1, 1, (1 - (-1)) / bin_num))
    return asdf.astype(np.uint8).tolist()


def digitize_tolist_dist(arr, bin_num=128):  # 5
    bx = np.linspace(0, 100, bin_num + 1)
    bxx = []

    for bxi in bx:
        bxx.append(np.percentile(arr, bxi))
    bxx[-1] = bxx[-1] + 1
    bxx[0] = bxx[0] - 1
    return np.digitize(arr, bxx).astype(np.uint8).tolist()


def ext_spectrogram(epoch, fs=1000, window='hamming', nperseg=2000, noverlap=1975, nfft=3000):
    # epoch.shape = channel number, timepoint, trials
    # extract sepctrogram with time point
    # here

    dat = []
    for i in range(epoch.shape[2]):
        tfreq = []
        for j in range(epoch.shape[0]):
            f, t, Sxx = signal.stft(epoch[j, :, i], fs=fs, window=window, nperseg=nperseg, noverlap=noverlap, nfft=nfft)
            # use frequency(~121th) and tiem(-41th~0)
            # tfreq.append(np.abs(Sxx[:121, -41:]).transpose()) # 40 Hz까지, 1초
            tfreq.append(np.abs(Sxx[:121, -61:]).transpose()) # 60 Hz까지, -1초~0.5초
            # tfreq.append(np.abs(Sxx[:121, :]).transpose())

        dat.append(np.asarray(tfreq))

    return np.array(dat)  # shape : (trials, channel number, time, freq), time and freq should be : 41, 121


def get_batch_num(data, batch_size):
    total_len = data.shape[0]
    return math.ceil(total_len / batch_size)


def get_batch(data, batch_size, idx):
    batch_num = get_batch_num(data, batch_size)
    if idx == batch_num - 1:  # last batch
        return data[batch_size * idx:]
    else:
        return data[batch_size * idx:batch_size * (idx + 1)]


# input: location
# output: train_x, train_y, test_x, test_y

def load_data_labels(location='dataset_original.mat'): #2.mat'):
    # load eeg data
    try:
        data = sio.loadmat(location)  # here
    except:
        data = mat73.loadmat(location)

    # get eeg data and extract spectogram
    # reshpae spectogram data as shape (num_trials, features) to use it in FC
    ep = ext_spectrogram(data['data_epoch']).reshape(data['data_epoch'].shape[2], -1)
    # (16, 3000, 260) -> (260, 16, 41, 121) -> (260, 79376)

    # get label data
    # reshape it to (num_trials, 1) to use it in FC
    # Y:\Research\EEG_kdj\EEG_preprocessed_mh\pilot_re_label_rpe\subj_002
    # dir_label_SPE = "Y:/Research/EEG_kdj/EEG_preprocessed_mh/pilot_re_label_rpe"
    dir_label_RPE = "Y:/Research/EEG_kdj/EEG_preprocessed_mh/pilot_re_label_rpe"
    subji = location[-32:-30]  # [-26:-24]
    if subji == "hj":
        subji = "1"
    elif subji == "yd":
        subji = "2"
    else:
        print("akakak")
    sessi = location[-29]

    # lb_data_SPE = sio.loadmat(dir_label_SPE + "/subj_{0}/sess{1}_spe_label".format(subji.zfill(3), sessi))
    lb_data_RPE = sio.loadmat(dir_label_RPE + "/subj_{0}/sess{1}_rpe_label".format(subji.zfill(3), sessi))
    # n_temp_SPE = "final_label_SPE_{0}_{1}".format(subji, sessi)
    n_temp_RPE = "final_label_RPE_{0}_{1}".format(subji, sessi)
    # lb_SPE = lb_data_SPE[n_temp_SPE].T  # (260, 1)
    lb_RPE = lb_data_RPE[n_temp_RPE].T

    # check shape of ep & lb
    # print(ep.shape, lb.shape)
    # generate random index, for unbiased dataset
    # shuffle_idx = np.arange(ep.shape[0])
    # np.random.shuffle(shuffle_idx)
    # shuffle ep and lb in the same order
    np.random.seed(2121)
    shuffle_idx = np.random.permutation(lb_RPE.shape[0])


    return ep[shuffle_idx], lb_RPE[shuffle_idx]



def load_data(location='dataset_original2.mat',is_total = False):
    # load eeg data
    data = sio.loadmat(location)
    # get eeg data and extract spectogram
    # reshpae spectogram data as shape (num_trials, features) to use it in FC
    ep = ext_spectrogram(data['ep']).reshape(data['ep'].shape[2], -1)
    # get label data
    # reshape it to (num_trials, 1) to use it in FC
    lb = data['lb'].T
    # check shape of ep & lb
    # print(ep.shape, lb.shape)
    # generate random index, for unbiased dataset
    # shuffle_idx = np.arange(ep.shape[0])
    # np.random.shuffle(shuffle_idx)
    # shuffle ep and lb in the same order
    if is_total:
        np.random.seed(2121)
        shuffle_idx = np.random.permutation(lb.shape[0])
        return ep[shuffle_idx], lb[shuffle_idx]
    else:
        shuffle_idx = np.random.permutation(lb.shape[0])
        ep = ep[shuffle_idx]
        lb = lb[shuffle_idx]
        num_train = int(ep.shape[0] * 9 / 10)
        return ep[:num_train], lb[:num_train], ep[num_train:], lb[num_train:]


class networks():
    def __init__(self, ep):
        # build network
        self.lr = 0.001
        # 0.00003 was good
        ####### 아래 애
        self.c_lr = 5e-6 #3e-7 #5e-6 #1e-6 #5e-7 # 5e-6 #3e-7 # 5e-6 #0.00003 # 3e-7  # 1e-8 # SPE : 3e-7
        self.training_epoch = 10000 #3000

        ##### 얘 조절하면
        self.c_training_epoch = 10000 #3000  # 2000
        # c_training_epoch = 2000 --> was good
        self.batch_size = 20 # 60?

        self.ep = ep
        self.num_input = self.ep.shape[1]

    def init_net(self):
        tf.reset_default_graph()

        # self.X = tf.placeholder(tf.float32, [None, self.num_input])
        # self.X = tf.placeholder(tf.float32, [None, 41, 121, 16])
        self.X = tf.placeholder(tf.float32, [None, 61, 121, 16])
        self.Y = tf.placeholder(tf.float32, [None, 1])
        # X = tf.placeholder(tf.float32, [None, 121*4, 41*4, 1])
        # Y = tf.placeholder(tf.float32, [None, 1])

        # bat_normzer = tf.layers.BatchNormalization()
        # self.norXm = bat_normzer(self.X)

        w1 = tf.get_variable("e_W1",shape=[5, 5, 16, 32], initializer=tf.keras.initializers.glorot_normal())
        conv1 = tf.nn.conv2d(self.X, w1, strides=[1, 2, 2, 1], padding="SAME")
        self.bn1 = tf.layers.batch_normalization(conv1) # tf.keras.layers.BatchNormalization
        self.conv1_out = tf.nn.relu(self.bn1)
        self.pool1 = tf.nn.max_pool(self.conv1_out, ksize=[1, 2, 2, 1], strides=[1, 1, 1, 1], padding='SAME')

        w2 = tf.get_variable("e_W2",shape=[5, 5, 32, 32], initializer=tf.keras.initializers.glorot_normal())
        conv2 = tf.nn.conv2d(self.pool1, w2, strides=[1, 2, 2, 1], padding="SAME")
        self.bn2 = tf.layers.batch_normalization(conv2)
        self.conv2_out = tf.nn.relu(self.bn2)
        self.pool2 = tf.nn.max_pool(self.conv2_out, ksize=[1, 2, 2, 1], strides=[1, 1, 1, 1], padding='SAME')

        w3 = tf.get_variable("e_W3",shape=[3, 3, 32, 64], initializer=tf.keras.initializers.glorot_normal())
        conv3 = tf.nn.conv2d(self.pool2, w3, strides=[1, 1, 1, 1], padding="SAME")
        self.bn3 = tf.layers.batch_normalization(conv3)
        self.conv3_out = tf.nn.relu(self.bn3)
        self.pool3 = tf.nn.max_pool(self.conv3_out, ksize=[1, 2, 2, 1], strides=[1, 1, 1, 1], padding='SAME')

        w4 = tf.get_variable("e_W4",shape=[3, 3, 64, 64], initializer=tf.keras.initializers.glorot_normal())
        conv4 = tf.nn.conv2d(self.pool3, w4, strides=[1, 1, 1, 1], padding="SAME")
        self.bn4 = tf.layers.batch_normalization(conv4)
        self.conv4_out = tf.nn.relu(self.bn4)
        self.pool4 = tf.nn.max_pool(self.conv4_out, ksize=[1, 2, 2, 1], strides=[1, 1, 1, 1], padding='SAME') # (?, 11, 31, 64) -> # (?, 16, 31, 64)

        # gap = tf.reduce_mean(tf.reshape(pool1, shape=(-1,80*27,1)), axis=1)
        # self.gap = tf.reduce_mean(tf.reshape(self.pool4, shape=(-1,11*31,64)), axis=2) #(?, 341)
        self.gap = tf.reduce_mean(tf.reshape(self.pool4, shape=(-1, 16 * 31, 64)), axis=2)  # (?, 341)

        # self.weight_ = tf.Variable(tf.zeros((11*31, 1), dtype=tf.float32), dtype=tf.float32) # (341, 1)
        self.weight_ = tf.Variable(tf.zeros((16 * 31, 1), dtype=tf.float32), dtype=tf.float32)  # (341, 1)
        self.bias_ = tf.Variable(tf.zeros((1), dtype=tf.float32), dtype=tf.float32) #(1, )
        self.c_logit2 = tf.matmul(self.gap, self.weight_) + self.bias_ #(?, 1) # == dense layer

        self.c_sigmoid = tf.nn.sigmoid(self.c_logit2) #(?, 1)

        # regularization l2 221129
        regularizer = tensorflow.nn.l2_loss(w1) + tensorflow.nn.l2_loss(w2) + tensorflow.nn.l2_loss(
            w3) + tensorflow.nn.l2_loss(w4)
        beta = 0.01 # SPE: 0.01

        self.c_loss_ = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(labels=self.Y, logits=self.c_logit2))  # ()
        self.c_loss = tf.reduce_mean(self.c_loss_ + beta * regularizer)


        # self.c_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=self.Y, logits=self.c_logit2)) # ()


        self.c_optimizer = tf.train.AdamOptimizer(self.c_lr).minimize(self.c_loss)
        self.predicted = tf.cast(tf.nn.sigmoid(self.c_logit2) > 0.5, dtype=tf.float32) # (?, 1)
        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.predicted, self.Y), dtype=tf.float32)) # ()

        # train_summary_path, val_summary_path = "E:/dnn_example/logs6/train", "E:/dnn_example/logs6/val"
        # train_writer, val_writer = tf.summary.FileWriter(train_summary_path), tf.summary.FileWriter(val_summary_path)
        self.saver = tf.train.Saver(tf.global_variables())



    def return_hidden_original(self, CV, epoch, dataset_idx_pr, ep, lb, strings_): #dataset_idx = 1 -> train, dataset_idx =2 -> test
        # kf = KFold(n_splits=10, shuffle=True)
        # kf.get_n_splits(lb)
        dataset_idx = dataset_idx_pr -1
        tenfold_hs = []
        accs = []
        losses = []

        dataset_set = ['train', 'test']
        dataset = dataset_set[dataset_idx]

        summary_total = []
        for _ in ['train', 'test']:
            # summary_total.append({"hidden": [], "accuracy": [], "loss": [], "epochs": []})
            summary_total.append({"accuracy": [], "loss": [], "epochs": []})


        ep_train, lb_train = ep, lb
        batch_num = get_batch_num(ep_train, self.batch_size)
        feed_dict_train = {self.X: ep_train, self.Y: lb_train}
        conv1_out, pool1, conv2_out, pool2, conv3_out, pool3, gap, c_logit2, c_sigmoid, accuracy_hidden, c_loss_hidden = sess.run(
            [self.conv1_out, self.pool1, self.conv2_out, self.pool2,
             self.conv3_out, self.pool3, self.gap, self.c_logit2, self.c_sigmoid, self.accuracy*100, self.c_loss], feed_dict=feed_dict_train)

        accs.append(accuracy_hidden)
        losses.append(c_loss_hidden)


        print(f'[ACCS] CV: {CV + 1} & accs = {accuracy_hidden}')
        print(f'[LOSS] CV: {CV + 1} & cost = {c_loss_hidden}')


        summary_total[dataset_idx]["accuracy"].append(accuracy_hidden)
        summary_total[dataset_idx]["loss"].append(c_loss_hidden)
        summary_total[dataset_idx]["epochs"].append(epoch)


        # '/cv{0}'.format(cv) + '/original/hidden' + str(epoch) + {'_train' or '_test'} + '.pkl'
        direc = strings_ + '/logs6/original/cv{0}'.format(CV) + f'/_{dataset}'
        # f_name_dataset = 'E:/dnn_example/logs/cv{0}'.format(CV) + f'/dataset{dataset}/hidden' + str(epoch) + '.pkl'
        if not os.path.exists(direc):
            os.makedirs(direc)
        with open(direc + '/hidden' + str(epoch) + '.pkl', 'wb') as f:  # open(f_name_dataset, 'wb') as f:
            pickle.dump(summary_total[dataset_idx], f)


        print('#' * 30)
        print(f'[ACCS] CV: AVG & accs = {np.mean(accs)}')
        print(f'[LOSS] CV: AVG & cost = {np.mean(losses)}')

        return accs, losses  # tenfold_infos, accs, losses



print("main")
save_all = False

if save_all:
    eps = []
    lbs = []
    # for dataset in [0,1,5]:
    for dataset in [0]:
        if not os.path.exists(f'./dataset{dataset}'):
            os.mkdir(f'./dataset{dataset}')
        print(f'dataset{dataset}')
        ep_tot, lb_tot = load_data(f'dataset{dataset}_parsed.mat', is_total=True)
        eps.append(ep_tot)
        lbs.append(lb_tot)

print("loading...")


ep_tots = []
lb_tots = []
name_list_1 = ['220523_hj_1_20220523_122723.mff', '220522_hj_2_20220523_123308.mff', '220522_hj_3_20220523_123904.mff',
               '220522_hj_4_20220523_124432.mff', '220522_hj_5_20220523_125014.mff', '220522_hj_6_20220523_125529.mff']
name_list_2 = ['220522_yd_1_20220523_012521.mff', '220522_yd_2_20220523_013037.mff', '220522_yd_3_20220523_013607.mff',
               '220522_yd_4_20220523_014034.mff', '220522_yd_5_20220523_014552.mff', '220522_yd_6_20220523_015055.mff']
name_list = [name_list_1, name_list_2]

subi_matching = [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 10, 3, 6, 13, 5, 8, 4, 14, 15, 1, 17, 11, 16, 18, 9, 2, 12, 7]

# for pilot
for subi in tqdm(range(2)):
    # Y:\Research\EEG_kdj\EEG_data_pilot\bcr_fil
    for sess_i in range(6):
        dir_epoch_ = "Y:/Research/EEG_kdj/EEG_data_pilot_fix/bcr_fil/"
        name_epoch_data = name_list[subi][sess_i]
        dir_epoch = dir_epoch_ + "epoched_" + name_epoch_data[:-4] + "_bcr_fil.mat"
        # ep_tots_, lb_SPE_tot, lb_RPE_tot = load_data_labels(dir_epoch)
        ep_tots_, lb_RPE_tot = load_data_labels(dir_epoch)
        #'./dat_sub/sub{0}.mat'.format(subi+1))  # original2
        # ep_tots_ = ep_tots_.reshape((ep_tots_.shape[0],16,121,41)) # (260, 79376) -> (260, 16, 121, 41)
        ep_tots_ = ep_tots_.reshape((ep_tots_.shape[0], 16, 121, 61))
        if len(ep_tots) == 0:
            ep_tots = ep_tots_
        else:
            ep_tots = np.concatenate((ep_tots, ep_tots_),axis=0)


        if len(lb_tots) == 0:
            # lb_tots.append(lb_SPE_tot)
            lb_tots.append(lb_RPE_tot)

        else:
            # lb_tots[0]=np.concatenate((lb_tots[0],lb_SPE_tot),axis=0)
            lb_tots[0]=np.concatenate((lb_tots[0],lb_RPE_tot),axis=0)



ep_tots = np.swapaxes(ep_tots,1,3) # (24564, 41, 121, 16) # (trials, time, freq, channel_num)


# strings_="./logs4cnn_"  +datetime.today().strftime('%Y%m%d-%H%M')+ "/"
strings_ = "./logs/"

kf = KFold(n_splits=10, shuffle=False)
for lbi in [0]: # lbi == # 0 : RPE
    # check what is lbi == # 0 : lb_maxrel_totm, 1: lb_pmb28_tot, 2: lb_pmb37_tot, 3: lb_act_tot
    lb_tot = lb_tots[lbi] #(4, 24564, 1)
    lb1idx = np.where(lb_tot == 0)[0]
    lb2idx = np.where(lb_tot == 1)[0]
    minidx=min(lb1idx.shape[0],lb2idx.shape[0]) # 1293, 975 -> 975
    lb1idx = lb1idx[:minidx]
    lb2idx = lb2idx[:minidx] # 갯수 맞춰서 레이블 1 0 인거 나눔
    lb_tot = np.concatenate((lb_tot[lb1idx],lb_tot[lb2idx])) # (11514, 1) # 7024 or 4660
    ep_tot = np.concatenate((ep_tots[lb1idx],ep_tots[lb2idx]),axis=0) #(11514, 41, 121, 16)


    np.random.seed(2020)
    index = np.random.permutation(ep_tot.shape[0])
    ep_tot = ep_tot[index]
    lb_tot = lb_tot[index]

    kf.get_n_splits(lb_tot)
    cv = 0 #2

    print("main2")
    for train_ind, test_ind in kf.split(lb_tot):
        ep, lb = ep_tot[train_ind], lb_tot[train_ind]
        test_x, test_y = ep_tot[test_ind], lb_tot[test_ind]

        cv += 1

        if cv > 0:
            network = networks(ep_tot)
            network.init_net()
            # acc = []
            # loss = []
            epoch = []
            summary = {}
            # if not os.path.exists('./cv{0}'.format(cv)):
            #     os.mkdir('./cv{0}'.format(cv))
            gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.900)

            with tf.Session(config=tf.ConfigProto(gpu_options=gpu_options)) as sess:
                saver = tf.train.Saver(tf.global_variables())
                # tf.summary.scalar('loss', network.c_loss)
                # tf.summary.scalar('accuracy', network.accuracy)
                # merged = tf.summary.merge_all()
                # train_summary_path, val_summary_path = strings_+ f'label{lbi+1}' + "/train",strings_+ f'label{lbi+1}' + "/test"
                summary_path = strings_ + "runs/" + f'runs_label{lbi + 1}/cv{cv}' #+ "/run"
                writer_mh = tf.summary.FileWriter(summary_path)

                sess.run(tf.global_variables_initializer())
                batch_size = network.batch_size
                batch_num = get_batch_num(ep, batch_size)
                batch_num_test = get_batch_num(test_x, batch_size)
                # feed_dict_train = {network.X: ep, network.Y: lb.reshape(-1,1)}
                feed_dict_val = {network.X: test_x, network.Y: test_y.reshape(-1,1)}

                # summary_total = []
                # for dataset in [0, 5]:
                #     summary_total.append({"accuracy": [], "loss": [],
                #                           "epochs": []})  # "information": [], "accuracy": [], "loss": [], "epochs": []})
                epochs = []
                costs = []
                early_stopping = EarlyStopping(label=lbi+1, cv=cv)
                # print("break before")
                for epoch in tqdm(range(network.c_training_epoch)):

                    total_cost = 0
                    total_acc = 0

                    # for training
                    for i in range(batch_num):
                        batch_ep = get_batch(ep, batch_size, i)
                        batch_lb = get_batch(lb, batch_size, i)
                        _, batch_cost, batch_acc = sess.run([network.c_optimizer, network.c_loss, network.accuracy],
                                                            feed_dict={network.X: batch_ep,
                                                                       network.Y: batch_lb})
                        total_cost += batch_cost
                        total_acc += batch_acc * batch_ep.shape[0]
                    if (epoch + 1) % 50 == 0:
                        print(f'[Classifier] Epoch: {epoch + 1} & Avg_cost = {total_cost / batch_num}')
                    costs.append(total_cost / batch_num)

                    summary_loss = tf.Summary(value=[tf.Summary.Value(tag="loss_train", simple_value=total_cost / batch_num)])
                    summary_acc = tf.Summary(value=[tf.Summary.Value(tag="acc_train", simple_value=total_acc / lb.shape[0])])
                    train_accss = total_acc / lb.shape[0]
                    # train_writer.add_summary(summary_loss, global_step=epoch + 1)
                    # train_writer.add_summary(summary_acc, global_step=epoch + 1)
                    # train_writer.flush()
                    writer_mh.add_summary(summary_loss, global_step=epoch + 1)
                    writer_mh.add_summary(summary_acc, global_step=epoch + 1)

                    total_cost = 0
                    total_acc = 0

                    # For validation
                    for i in range(batch_num_test):
                        batch_ep = get_batch(test_x, batch_size, i)
                        batch_lb = get_batch(test_y, batch_size, i)
                        batch_cost, batch_acc = sess.run([network.c_loss, network.accuracy],
                                                            feed_dict={network.X: batch_ep,
                                                                       network.Y: batch_lb})
                        total_cost += batch_cost
                        total_acc += batch_acc * batch_ep.shape[0]


                    summary_loss = tf.Summary(value=[tf.Summary.Value(tag="loss_val", simple_value=total_cost / batch_num_test)])
                    summary_acc = tf.Summary(value=[tf.Summary.Value(tag="acc_val", simple_value=total_acc / test_y.shape[0])])
                    test_accss = total_acc / test_y.shape[0]
                    test_losss = total_cost / batch_num
                    writer_mh.add_summary(summary_loss, global_step=epoch + 1)
                    writer_mh.add_summary(summary_acc, global_step=epoch + 1)
                    writer_mh.flush()

                    # early_stopping(test_accss, saver)
                    # early_stopping(test_losss, saver)

                    # if early_stopping.early_stop:
                    #     print("Early stopping")
                    #     break


                    if (epoch + 1) % 50 == 0:
                        print(f'Test Accuracy: {test_accss}')
                        print(f'Train Accuracy: {train_accss}')
                        print(f'[Classifier] Epoch: {epoch + 1} & Test_cost = {test_losss}')


                    # if (epoch + 1) == 100:
                    #     if not os.path.exists(strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1) + str(epoch + 1)):
                    #         os.makedirs(strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1)  + str(epoch + 1))
                    #     saver.save(sess,strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1) + str(epoch + 1) + '/dnn.ckpt')

                    if (epoch + 1) % 1000 == 0:
                        if not os.path.exists(strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1)  + str(epoch + 1)):
                            os.makedirs(strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1)  + str(epoch + 1))
                        saver.save(sess, strings_ + '/cv{0}/label{1}/model_'.format(cv,lbi+1) + str(epoch + 1) + '/dnn.ckpt')

                    if save_all:
                        if (epoch + 1) % 50 == 0:
                            # train data
                            # acc1, loss1 = network.return_hidden_original(cv, epoch, 1, ep, lb, strings_)
                            # test data
                            acc2, loss2 = network.return_hidden_original(cv, epoch, 2, test_x, test_y, strings_)


                # print("break after")