import argparse
import joblib
from deep_ifs.utils.datasets import *
from sklearn.ensemble import ExtraTreesRegressor
from deep_ifs.utils.Logger import Logger
from deep_ifs.utils.timer import *
from deep_ifs.extraction.Autoencoder import Autoencoder
from deep_ifs.selection.ifs import IFS

# Args
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', action='store_true',
                    help='Run in debug mode')
parser.add_argument('--load-ae', type=str, default=None,
                    help='Path to h5 weights file to load into AE')
parser.add_argument('--load-sars', type=str, default=None,
                    help='Path to dataset folder to use instead of collecting')
parser.add_argument('--binarize', action='store_true',
                    help='Binarize input to the neural networks')
parser.add_argument('--save-FAR', action='store_true',
                    help='Save the FA, R arrays')
parser.add_argument('--load-FAR', type=str, default=None,
                    help='Load the FA, R arrays')
args = parser.parse_args()

# Parameters
nn_nb_epochs = 5 if args.debug else 300  # Number of training epochs for NNs
nn_batch_size = 6 if args.debug else 32  # Number of samples in a batch for AE
nn_encoding_dim = 512
ifs_nb_trees = 50  # Number of trees to use in IFS
ifs_significance = 1  # Significance for IFS

# Setup
logger = Logger(output_folder='../output/',
                custom_run_name='ifs_pre%Y%m%d-%H%M%S')
setup_logging(logger.path + 'log.txt')

# Load SARS dataset
sars_path = args.load_sars
samples_in_dataset = get_nb_samples_from_disk(sars_path)

# Autoencoder
log('Loading AE from %s' % args.load_ae)
target_size = 1  # Target is the scalar reward
ae = Autoencoder((4, 108, 84),
                 nb_epochs=nn_nb_epochs,
                 encoding_dim=nn_encoding_dim,
                 binarize=args.binarize,
                 logger=logger,
                 ckpt_file='autoencoder_ckpt.h5')
ae.load(args.load_ae)
ae.model.summary()

# Build dataset for IFS
if args.load_FAR is None:
    log('Building dataset')
    assert sars_path is not None, 'Please provide a SARS dataset'
    FA, R = build_far_from_disk(ae, sars_path)
    if args.save_FAR:
        joblib.dump((FA, R), logger.path + 'FA_R.pkl')
else:
    log('Loading FA, R from %s' % args.load_FAR)
    FA, R = joblib.load(args.load_FAR)

# Run IFS
log('Running IFS')
ifs_estimator_params = {'n_estimators': ifs_nb_trees,
                        'n_jobs': -1}
ifs_params = {'estimator': ExtraTreesRegressor(**ifs_estimator_params),
              'n_features_step': 1,
              'cv': None,
              'scale': True,
              'verbose': 2,
              'significance': ifs_significance}
ifs = IFS(**ifs_params)
preload_features = range(FA.shape[1] - 1)  # All F except one so that IFS will print R2
ifs.fit(FA, R, preload_features=preload_features)

# Get support
support = ifs.get_support()
got_action = support[-1]  # Action is the last feature
support = support[:-1]  # Remove action from support
nb_new_features = np.array(support).sum()
log('Features: %s' % np.array(support).nonzero())
log('IFS - New features: %s' % nb_new_features)
log('Action was%s selected' % ('' if got_action else ' NOT'))