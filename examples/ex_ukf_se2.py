from pynav.lib.states import SE3State
from pynav.lib.models import BodyFrameVelocity, RangePoseToAnchor
from pynav.datagen import DataGenerator
from pynav.filters import ExtendedKalmanFilter, IteratedKalmanFilter, SigmaPointKalmanFilter
from pynav.utils import GaussianResult, GaussianResultList, plot_error, randvec
from pynav.types import StateWithCovariance
import time
from pylie import SE3
import numpy as np
from typing import List
np.random.seed(0)

# ##############################################################################
# Problem Setup
x0 = SE3State(SE3.Exp([0, 0, 0, 0, 0, 0]), stamp=0.0, direction="right")
P0 = np.diag([0.1**2, 0.1**2, 0.1**2, 1, 1, 1])
Q = np.diag([0.01**2, 0.01**2, 0.01**2, 0.1, 0.1, 0.1])
process_model = BodyFrameVelocity(Q)
noise_active = True

def input_profile(t, x):
    return np.array(
        [np.sin(0.1 * t), np.cos(0.1 * t), np.sin(0.1 * t), 1, 0, 0]
    )


range_models = [
    RangePoseToAnchor([1, 0, 0], [0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([1, 0, 0], [-0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([-1, 0, 0], [0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([-1, 0, 0], [-0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([0, 2, 0], [0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([0, 2, 0], [-0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([0, 2, 2], [0.17, 0.17, 0], 0.1**2),
    RangePoseToAnchor([0, 2, 2], [-0.17, 0.17, 0], 0.1**2),
]

# ##############################################################################
# Data Generation
dg = DataGenerator(process_model, input_profile, Q, 200, range_models, 10)
state_true, input_data, meas_data = dg.generate(x0, 0, 10, noise=noise_active)

if noise_active:
    x0 = x0.plus(randvec(P0))
# %% ###########################################################################
# Run Filter
x = StateWithCovariance(x0, P0)

# Try an EKF or an IterEKF
# ekf = ExtendedKalmanFilter(process_model)
ukf = SigmaPointKalmanFilter(process_model, method = 'cubature', iterate_mean=True)

meas_idx = 0
start_time = time.time()
y = meas_data[meas_idx]
results_list = []
for k in range(len(input_data) - 1):
    results_list.append(GaussianResult(x, state_true[k]))

    u = input_data[k]
    
    # Fuse any measurements that have occurred.
    while y.stamp < input_data[k + 1].stamp and meas_idx < len(meas_data):

        x = ukf.correct(x, y, u)
        meas_idx += 1
        if meas_idx < len(meas_data):
            y = meas_data[meas_idx]

    dt = input_data[k + 1].stamp - x.stamp
    x = ukf.predict(x, u, dt)
    


print("Average filter computation frequency (Hz):")
print(1 / ((time.time() - start_time) / len(input_data)))

results = GaussianResultList(results_list)

# ##############################################################################
# Plot
import seaborn as sns
import matplotlib.pyplot as plt

sns.set_theme()
fig, axs = plot_error(results)
axs[-1][0].set_xlabel("Time (s)")
axs[-1][1].set_xlabel("Time (s)")
axs[0][0].set_title("Rotation Error")
axs[0][1].set_title("Translation Error")
plt.show()
