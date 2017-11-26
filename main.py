import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests


# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion('1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn('No GPU found. Please use a GPU to train your neural network.')
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))


def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """
    vgg_tag = 'vgg16'
    vgg_input_tensor_name = 'image_input:0'
    vgg_keep_prob_tensor_name = 'keep_prob:0'
    vgg_layer3_out_tensor_name = 'layer3_out:0'
    vgg_layer4_out_tensor_name = 'layer4_out:0'
    vgg_layer7_out_tensor_name = 'layer7_out:0'
    
    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)

    graph = tf.get_default_graph()
    vgg_input = graph.get_tensor_by_name(vgg_input_tensor_name)
    keep = graph.get_tensor_by_name(vgg_keep_prob_tensor_name)
    layer3 = graph.get_tensor_by_name(vgg_layer3_out_tensor_name)
    layer4 = graph.get_tensor_by_name(vgg_layer4_out_tensor_name)
    layer7 = graph.get_tensor_by_name(vgg_layer7_out_tensor_name)

    return vgg_input, keep, layer3, layer4, layer7
tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    Uses 2 skip layers, and 2 hidden layers.  Pools after each full layer.
    :param vgg_layer7_out: TF Tensor for VGG Layer 3 output
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 output
    :param vgg_layer3_out: TF Tensor for VGG Layer 7 output
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of output
    """

    regularizer = tf.contrib.layers.l2_regularizer(1e-3)
    initializer = tf.contrib.layers.xavier_initializer()

    fcn_layer_1 = tf.layers.conv2d(vgg_layer7_out, num_classes, 1, strides=(1,1),
                                  padding='same',
                                  kernel_initializer=initializer,
                                  kernel_regularizer=regularizer)

    fcn_layer_2 = tf.layers.conv2d(vgg_layer4_out, num_classes, 1, strides=(1,1),
                                padding='same',
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer)

    fcn_layer_3 = tf.layers.conv2d(vgg_layer3_out, num_classes, 1, strides=(1,1),
                                padding='same',
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer)

    transpose_1 = tf.layers.conv2d_transpose(fcn_layer_1, num_classes, 4, strides=(2, 2),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    skip_1 = tf.add(transpose_1, fcn_layer_2)

    transpose_2 = tf.layers.conv2d_transpose(skip_1, num_classes, 4, strides=(2, 2),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    skip_2 = tf.add(transpose_2, fcn_layer_3)

    transpose_3 = tf.layers.conv2d_transpose(skip_2, num_classes, 8, strides=(4, 4),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    hl_1 = tf.layers.conv2d(transpose_3, num_classes, 3, strides=(1, 1),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    hl_1_pool = tf.layers.average_pooling2d(hl_1, pool_size=(3, 3), strides=(2, 2),
                                padding='same')

    hl_1_transpose = tf.layers.conv2d_transpose(hl_1_pool, num_classes, 8, strides=(4, 4),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    hl_2 = tf.layers.conv2d(hl_1_transpose, num_classes, 3, strides=(1, 1),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    hl_2_pool = tf.layers.average_pooling2d(hl_2, pool_size=(3, 3), strides=(2, 2),
                                padding='same')

    hl_2_transpose = tf.layers.conv2d_transpose(hl_2_pool, num_classes, 8, strides=(4, 4),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    output = tf.layers.conv2d(hl_2_transpose, num_classes, 3, strides=(1, 1),
                                kernel_initializer=initializer,
                                kernel_regularizer=regularizer,
                                padding='same')

    nn_last_layer = tf.layers.average_pooling2d(output, pool_size=(3, 3), strides=(2, 2),
                                padding='same')

    return nn_last_layer
tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """
    logits = tf.reshape(nn_last_layer, (-1, num_classes))
    cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=correct_label)) 
    trainer = tf.train.AdamOptimizer(learning_rate=learning_rate)
    train_op = trainer.minimize(cross_entropy_loss, var_list=tf.trainable_variables())

    return logits, train_op, cross_entropy_loss
tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.  Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """
    for epoch in range(epochs):
        total_loss = 0
        batch = 0
        for train_data, label_data in get_batches_fn(batch_size):
            feed_dict={input_image: train_data, correct_label: label_data, learning_rate: 0.001, keep_prob: 0.9}
            _, loss = sess.run([train_op, cross_entropy_loss], feed_dict)
            batch += 1

        total_loss += loss
        print("Epoch: {} - Loss: {}".format(epoch, total_loss))
tests.test_train_nn(train_nn)


def run():
    epochs = 20
    batch_size=5
    num_classes = 2
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    # Download pretrained vgg model
    helper.maybe_download_pretrained_vgg(data_dir)

    # OPTIONAL: Train and Inference on the cityscapes dataset instead of the Kitti dataset.
    # You'll need a GPU with at least 10 teraFLOPS to train on.
    #  https://www.cityscapes-dataset.com/

    with tf.Session() as sess:
        # Path to vgg model
        vgg_path = os.path.join(data_dir, 'vgg')
        # Create function to get batches
        get_batches_fn = helper.gen_batch_function(os.path.join(data_dir, 'data_road/training'), image_shape)

        # OPTIONAL: Augment Images for better results
        #  https://datascience.stackexchange.com/questions/5224/how-to-prepare-augment-images-for-neural-network

        # Build NN using load_vgg, layers, and optimize function
        input_image, keep_prob_layer, vgg_layer_3, vgg_layer_4, vgg_layer_7 = load_vgg(sess, vgg_path)
        layer_output = layers(vgg_layer_3, vgg_layer_4, vgg_layer_7, num_classes)
        correct_label = tf.placeholder(tf.float32, [None, image_shape[0], image_shape[1], num_classes])
        learning_rate = tf.placeholder(tf.float32)
        logits, train_op, cross_entropy_loss = optimize(layer_output, correct_label, learning_rate, num_classes)
        sess.run(tf.global_variables_initializer())

        # Train NN using the train_nn function
        train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, 
            input_image, correct_label, keep_prob_layer, learning_rate)
        
        # Save inference data using helper.save_inference_samples
        helper.save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob_layer, input_image)

        # OPTIONAL: Apply the trained model to a video


if __name__ == '__main__':
    run()
