# from models.generators import ResnetG
# from synth_data_2d import plot_data
# from models.resnet9_ntk import ResNet
import random

import torch as pt

from models.ntk import *


# from util import plot_mnist_batch, log_final_score


def synthesize_mnist_with_uniform_labels(gen, device, gen_batch_size=1000, n_data=60000, n_labels=10):
    gen.eval()
    assert n_data % gen_batch_size == 0
    assert gen_batch_size % n_labels == 0
    n_iterations = n_data // gen_batch_size

    data_list = []
    ordered_labels = pt.repeat_interleave(pt.arange(n_labels), gen_batch_size // n_labels)[:, None].to(device)
    labels_list = [ordered_labels] * n_iterations

    with pt.no_grad():
        for idx in range(n_iterations):
            gen_code, gen_labels = gen.get_code(gen_batch_size, device, labels=ordered_labels)
            gen_samples = gen(gen_code)
            data_list.append(gen_samples)
    return pt.cat(data_list, dim=0).cpu().numpy(), pt.cat(labels_list, dim=0).cpu().numpy()


def calc_mean_emb1(model_ntk, ar, device, train_loader, n_classes):
    random.seed(ar.seed)
    pt.manual_seed(ar.seed)

    """ initialize the variables"""

    mean_v_samp = torch.Tensor([]).to(device)
    for p in model_ntk.parameters():
        mean_v_samp = torch.cat((mean_v_samp, p.flatten()))
    d = len(mean_v_samp)
    mean_emb1 = torch.zeros((d, n_classes), device=device)
    print('Feature Length:', d)
    n_data = 0
    # for a batch
    for it, data_all in enumerate(train_loader):
        data, labels = data_all[0], data_all[1]
        n_data += data.shape[0]
        data, y_train = data.to(device), labels.to(device)
        # for single pieces of data
        for i in range(data.shape[0]):
            """ manually set the weight if needed """
            # model_ntk.fc1.weight = torch.nn.Parameter(output_weights[y_train[i],:][None,:])

            mean_v_samp = torch.Tensor([]).to(device)  # sample mean vector init
            if ar.data == 'cifar10':
                f_x = model_ntk(data[i][None, :, :, :])  # 1 input, dimensions need tweaking
            else:
                f_x = model_ntk(data[i][None, :])

            """ get NTK features """
            f_idx_grad = torch.autograd.grad(f_x, model_ntk.parameters(),
                                             grad_outputs=f_x.data.new(f_x.shape).fill_(1))
            for g in f_idx_grad:
                mean_v_samp = torch.cat((mean_v_samp, g.flatten()))

            """ normalize the sample mean vector """
            m = mean_v_samp / torch.norm(mean_v_samp)
            if ar.data != 'cifar10':
                m = m[:, None]
            mean_emb1[:, y_train[i].long()] += m

    """ average by class count """
    print(mean_emb1.shape)
    print(n_data)
    mean_emb1 = torch.div(mean_emb1, n_data)
    print("This is the shape for dp-ntk mean_emb1: ", mean_emb1.shape)

    """ save model for downstream task """
    torch.save(mean_emb1, ar.log_dir + 'mean_emb1_' + str(d) + '.pth')

    torch.save(model_ntk.state_dict(), ar.log_dir + 'model_' + str(d) + '.pth')
