from mock import Mock
import numpy as np
import pytest
import importlib
import theano
from theano.tensor.nnet import conv2d

from lasagne.utils import floatX


def conv2d_test_sets():
    def _convert(input, kernel, output, kwargs):
        return [theano.shared(floatX(input)), floatX(kernel), output, kwargs]

    for border_mode in ['valid', 'full', 'same']:
        conv_mode = 'full' if border_mode == 'same' else border_mode

        for stride in [1, 2, 3]:
            input = np.random.random((3, 1, 16, 23))
            kernel = np.random.random((16, 1, 3, 3))
            output = conv2d(input, kernel,
                            border_mode=conv_mode,
                            ).eval()
            if border_mode == 'same':
                shift_x = (kernel.shape[2] - 1) // 2
                shift_y = (kernel.shape[3] - 1) // 2
                output = output[:, :, shift_x:input.shape[2] + shift_x,
                                shift_y:input.shape[3] + shift_y]
            output = output[:, :, ::stride, ::stride]
            yield _convert(input, kernel, output, {'border_mode': border_mode,
                                                   'strides': (stride, stride)
                                                   })

            input = np.random.random((3, 3, 16, 23))
            kernel = np.random.random((16, 3, 3, 3))
            output = conv2d(input, kernel,
                            border_mode=conv_mode,
                            ).eval()
            if border_mode == 'same':
                shift_x = (kernel.shape[2] - 1) // 2
                shift_y = (kernel.shape[3] - 1) // 2
                output = output[:, :, shift_x:input.shape[2] + shift_x,
                                shift_y:input.shape[3] + shift_y]
            output = output[:, :, ::stride, ::stride]
            yield _convert(input, kernel, output, {'border_mode': border_mode,
                                                   'strides': (stride, stride)
                                                   })


@pytest.fixture
def DummyInputLayer():
    def factory(get_output_shape):
        return Mock(
            get_output_shape=lambda: get_output_shape,
            get_output=lambda input: input,
            )
    return factory


class TestConv2DLayerImplementations:
    @pytest.fixture(
        params=[
            ('lasagne.layers', 'Conv2DLayer', {}),
            ('lasagne.layers.cuda_convnet',
             'Conv2DCCLayer',
             {'flip_filters': True}),
            ('lasagne.layers.corrmm', 'Conv2DMMLayer', {'flip_filters': True}),
            ('lasagne.layers.dnn', 'Conv2DDNNLayer', {'flip_filters': True}),
            ],
        )
    def Conv2DImpl(self, request):
        impl_module_name, impl_name, impl_default_kwargs = request.param
        try:
            mod = importlib.import_module(impl_module_name)
        except ImportError:
            pytest.skip("{} not available".format(impl_module_name))

        impl = getattr(mod, impl_name)

        def wrapper(*args, **kwargs):
            kwargs2 = impl_default_kwargs.copy()
            kwargs2.update(kwargs)
            return impl(*args, **kwargs2)

        wrapper.__name__ = impl_name
        return wrapper

    @pytest.mark.parametrize(
        "input, kernel, output, kwargs", list(conv2d_test_sets()))
    @pytest.mark.parametrize("extra_kwargs", [
        {},
        {'untie_biases': True},
        ])
    def test_defaults(self, Conv2DImpl, DummyInputLayer,
                      input, kernel, output, kwargs, extra_kwargs):
        kwargs.update(extra_kwargs)
        b, c, h, w = input.shape.eval()
        input_layer = DummyInputLayer((b, c, h, w))
        try:
            layer = Conv2DImpl(
                input_layer,
                num_filters=kernel.shape[0],
                filter_size=kernel.shape[2:],
                W=kernel,
                **kwargs
                )
            actual = layer.get_output(input).eval()
            assert actual.shape == output.shape
            assert actual.shape == layer.get_output_shape()
            assert np.allclose(actual, output)

        except NotImplementedError:
            pass

    @pytest.mark.parametrize(
        "input, kernel, output, kwargs", list(conv2d_test_sets()))
    def test_with_nones(self, Conv2DImpl, DummyInputLayer,
                        input, kernel, output, kwargs):
        b, c, h, w = input.shape.eval()
        input_layer = DummyInputLayer((None, c, None, None))
        try:
            layer = Conv2DImpl(
                input_layer,
                num_filters=kernel.shape[0],
                filter_size=kernel.shape[2:],
                W=kernel,
                **kwargs
                )
            actual = layer.get_output(input).eval()

            assert layer.get_output_shape() == (None,
                                                kernel.shape[0],
                                                None,
                                                None)
            assert actual.shape == output.shape
            assert np.allclose(actual, output)

        except NotImplementedError:
            pass
