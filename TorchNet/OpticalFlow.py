import torch
import torch.nn as nn
import torch.nn.functional as F


class Pad67to68(nn.Module):
    def __init__(self):
        super(Pad67to68, self).__init__()
        self.pad = nn.ReflectionPad2d((0, 0, 0, 1))

    def forward(self, input):
        return self.pad(input)


class _CoarseFlow(nn.Module):
    """
    Coarse Flow Network in MCT
    |----------------------|
    |    Input two frame   |
    |----------------------|
    | Conv k5-n24-s2, ReLu |
    |----------------------|
    | Conv k3-n24-s1, ReLu |
    |----------------------|
    | Conv k5-n24-s2, ReLu |
    |----------------------|
    | Conv k3-n24-s1, ReLu |
    |----------------------|
    | Conv k3-n32-s1, Tanh |
    |----------------------|
    |   Pixel Shuffle x4   |
    |----------------------|
    """
    def __init__(self, input_channel=1):
        super(_CoarseFlow, self).__init__()
        self.channel = input_channel
        self.conv1 = nn.Conv2d(input_channel * 2, 24, 5, stride=2, padding=2)
        self.conv2 = nn.Conv2d(24, 24, 3, stride=1, padding=1)
        self.conv3 = nn.Conv2d(24, 24, 5, stride=2, padding=2)
        self.conv4 = nn.Conv2d(24, 24, 3, stride=1, padding=1)
        self.conv5 = nn.Conv2d(24, 32, 3, stride=1, padding=1)
        self.pix = nn.PixelShuffle(4)

    def forward(self, frame_t, frame_tp1):
        input = torch.cat([frame_t, frame_tp1], dim=1)
        return self.pix(
            F.tanh(self.conv5(
                F.relu(self.conv4(
                    F.relu(self.conv3(
                        F.relu(self.conv2(
                            F.relu(self.conv1(input))
                        ))
                    ))
                ))
            ))
        )


class _FineFlow(nn.Module):
    """
    Fine Flow Network in MCT
    |----------------------|
    |    Input two frame   |
    |----------------------|
    | Conv k5-n24-s2, ReLu |
    |----------------------|
    | Conv k3-n24-s1, ReLu |
    |----------------------|
    | Conv k3-n24-s1, ReLu |
    |----------------------|
    | Conv k3-n24-s1, ReLu |
    |----------------------|
    |  Conv k3-n8-s1, Tanh |
    |----------------------|
    |   Pixel Shuffle x2   |
    |----------------------|
    """
    def __init__(self, input_channel=1):
        super(_FineFlow, self).__init__()
        self.channel = input_channel
        self.conv1 = nn.Conv2d(input_channel * 3 + 2, 24, 5, stride=2, padding=2)
        self.conv2 = nn.Conv2d(24, 24, 3, stride=1, padding=1)
        self.conv3 = nn.Conv2d(24, 24, 3, stride=1, padding=1)
        self.conv4 = nn.Conv2d(24, 24, 3, stride=1, padding=1)
        self.conv5 = nn.Conv2d(24, 8, 3, stride=1, padding=1)
        self.pix = nn.PixelShuffle(2)

    def forward(self, frame_t, frame_tp1, flow, coarse_frame_tp1):
        input = torch.cat([frame_t, frame_tp1, flow, coarse_frame_tp1], dim=1)
        return self.pix(
            F.tanh(self.conv5(
                F.relu(self.conv4(
                    F.relu(self.conv3(
                        F.relu(self.conv2(
                            F.relu(self.conv1(input))
                        ))
                    ))
                ))
            ))
        )


class Warp(nn.Module):
    """
    Warp new frame using flow field
    Given an input and a flow-field grid, computes the output using input pixel locations from the grid.
    Uses bilinear interpolation to sample the input pixels. Currently, only spatial (4 dimensional) inputs are supported.
    For each output location, grid has x and y input pixel locations which are used to compute output.
    flow field has values in the range of [-1, 1]. This is because the pixel locations are normalized by the input height and width.
    """
    def __init__(self):
        super(Warp, self).__init__()

    def forward(self, frame_t, flow_field):
        """
        :param frame_t: input batch of images (N x C x IH x IW)
        :param flow_field: flow_field with shape(N x 2 x OH x OW)
        :return: output Tensor
        """
        return F.grid_sample(frame_t, flow_field.permute([0, 2, 3, 1]))


class FlowField(nn.Module):
    """
    The final Fine Flow
    """
    def __init__(self):
        super(FlowField, self).__init__()
        self.coarse_net = _CoarseFlow()
        self.fine_net = _FineFlow()
        self.warp = Warp()

    def forward(self, frame_t, frame_tp1):
        coarse_flow = self.coarse_net(frame_t, frame_tp1)
        coarse_frame_tp1 = self.warp(frame_t, coarse_flow)
        return self.fine_net(frame_t, frame_tp1, coarse_flow, coarse_frame_tp1) + coarse_flow






