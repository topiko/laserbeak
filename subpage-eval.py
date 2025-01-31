"""
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch import Tensor
import numpy as np
import math
import os
from os.path import join
import pickle as pkl
from tqdm import tqdm
from torchvision import transforms, utils
import transformers
import scipy
import json
import time
import argparse

from laserbeak.data import *
from laserbeak.transdfnet import DFNet
from laserbeak.processor import DataProcessor
from laserbeak.cls_cvt import ConvolutionalVisionTransformer



# enable if NaN or other odd behavior appears
#torch.autograd.set_detect_anomaly(True)
# disable any unnecessary logging / debugging
torch.autograd.set_detect_anomaly(False)
torch.autograd.profiler.profile(False)
torch.autograd.profiler.emit_nvtx(False)

# auto-optimize cudnn ops
torch.backends.cudnn.benchmark = True

def parse_args():
    parser = argparse.ArgumentParser(
                        prog = 'WF Benchmark',
                        description = 'Train & evaluate WF attack model.',
                        epilog = 'Text at the bottom of help')
    parser.add_argument('--data_dir',
                        default = './data',
                        type = str,
                        help = "Set root data directory.")
    parser.add_argument('--results_dir',
                        default = './results',
                        type = str,
                        help = "Set directory for result logs.")
    parser.add_argument('--ckpt',
                        default = None,
                        type = str,
                        help = "Resume from checkpoint path.")
    parser.add_argument('--dataset',
                        default = DATASET_CHOICES[0],
                        type = str,
                        choices = DATASET_CHOICES,
                        help = "Select dataset for train & test.")
    parser.add_argument('--bs',
                        default = 128,
                        type = int,
                        help = "Training batch size.")
    parser.add_argument('--use_tmp',
                        action = 'store_true',
                        default=False,
                        help = "Store data post transformation to disk to save memory.")
    parser.add_argument('--tmp_name',
                        default = None,
                        help = "The name of the subdirectory in which to store data.")
    parser.add_argument('--keep_tmp',
                        action = 'store_true',
                        default=False,
                        help = "Do not clear processed data files upon program completion.")
    parser.add_argument('--run_cvt',
                        action = 'store_true',
                        default=False,
                        help="Use Convolutional Vision Transformer model.")
    return parser.parse_args()




if __name__ == "__main__":
    """
    """
    args = parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # load checkpoint (if it exists)
    checkpoint_path = args.ckpt
    checkpoint_fname = None
    resumed = None
    if checkpoint_path and os.path.exists(checkpoint_path):
        print("Resuming from checkpoint...")
        resumed = torch.load(checkpoint_path)
        checkpoint_fname = os.path.basename(os.path.dirname(checkpoint_path))
    else:
        print("No valid checkpoint!")
        import sys
        sys.exit()
    # else: checkpoint path and fname will be defined later if missing

    eval_only = True
    root = args.data_dir
    results_dir = args.results_dir
    dataset = args.dataset

    if args.run_cvt:
        model_name = "CvT"
    else:
        model_name = "DF"

    # # # # # #
    mini_batch_size = args.bs   # samples to fit on GPU
    batch_size = args.bs        # when to update model
    accum = batch_size // mini_batch_size
    include_unm = False

    # all trainable network parameters
    params = []

    model_config = resumed['config']

    print("==> Model configuration:")
    print(json.dumps(model_config, indent=4))


    # # # # # #
    # create data loaders
    # # # # # #
    processor = DataProcessor(model_config['feature_list'])
    input_channels = processor.input_channels

    # processing applied to samples on dataset load
    tr_transforms = [
                        ToTensor(),
                        ToProcessed(processor),
                    ]
    te_transforms = [
                        ToTensor(),
                        ToProcessed(processor),
                    ]
    # processing applied to batch samples during training
    tr_augments = [
                    ]
    te_augments = [
                    ]

    trainloader, valloader, testloader, classes = load_data(dataset,
                                                 batch_size = mini_batch_size,
                                                 tr_transforms = tr_transforms,
                                                 te_transforms = te_transforms,
                                                 tr_augments = tr_augments,
                                                 te_augments = te_augments,
                                                 include_unm = include_unm,
                                                 multisample_count = 1,
                                                 tmp_root = './tmp' if args.use_tmp else None,
                                                 tmp_subdir = args.tmp_name,
                                                 keep_tmp = args.keep_tmp,
                                                 subpage_as_labels = True,
                                                )
    print(classes)
    unm_class = classes-1 if include_unm else -1

    # # # # # #
    # define base metaformer model
    # # # # # #
    if args.run_cvt:
        net = ConvolutionalVisionTransformer(in_chans=input_channels).to(device)
    else:
        net = DFNet(classes, input_channels,
                    **model_config)
        net = net.to(device)
        if resumed:
            net_state_dict = resumed['model']
            net.load_state_dict(net_state_dict)

    criterion = nn.CrossEntropyLoss(
                                    reduction = 'mean',
                                )

    def test_iter(i):
        """
        """
        test_loss = 0.
        test_acc = 0
        n = 0
        res = np.zeros((classes, 4))
        with tqdm(testloader, desc=f"Test", bar_format='{l_bar}{bar:10}{r_bar}{bar:-10b}', dynamic_ncols=True) as pbar:
            for batch_idx, (inputs, targets, sample_sizes) in enumerate(pbar):

                inputs, targets = inputs.to(device), targets.to(device)
                if inputs.size(0) <= 1: continue

                # # # # # #
                # DF prediction
                cls_pred = net(inputs)
                loss = criterion(cls_pred, targets)

                test_loss += loss.item()

                soft_res = F.softmax(cls_pred, dim=1)
                y_prob, y_pred = soft_res.max(1)
                test_acc += torch.sum(y_pred == targets).item()
                n += len(targets)

                for j in range(len(y_pred)):
                    label = targets[j]
                    prob = y_prob[j]
                    pred = y_pred[j]
                    for cls in range(classes):
                        if cls == label and label == pred:
                            res[cls][0] += 1  # TP
                        elif cls == label and label != pred:
                            res[cls][3] += 1  # FN
                        elif cls != label and pred == cls:
                            res[cls][2] += 1  # FP
                        elif cls != label:
                            res[cls][1] += 1  # TN
                        else:
                            print(pred, label)

                pbar.set_postfix({
                                  'acc': test_acc/n,
                                  'loss': test_loss/(batch_idx+1),
                                })

        # print results
        for i in range(classes):
            t = res[i][0] + res[i][3]
            rec = (res[i][0] / t) if t > 0 else 0
            t = res[i][0] + res[i][2]
            pre = (res[i][0] / t) if t > 0 else 0
            f1 = 2 * (pre * rec) / (pre + rec)
            if pre > 0 and rec > 0:
                print(f"{i}:\t{int(res[i][0])}\t{int(res[i][1])}\t{int(res[i][2])}\t{int(res[i][3])}\t{pre:.3f}\t{rec:.3f}\t{f1:.3f}")

        test_loss /= batch_idx + 1
        test_acc /= n
        return test_loss, test_acc


    if resumed:
        net.eval()

        epoch = -1
        test_loss, test_acc = test_iter(epoch)
        print(f'[{epoch}] te. loss ({test_loss:0.3f}), te. acc ({test_acc:0.3f})')
    else:
        print(f'Could not load checkpoint [{checkpoint_path}]: Path does not exist')
