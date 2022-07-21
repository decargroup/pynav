from pynav.filters import ExtendedKalmanFilter
from pynav.states import VectorState
from pynav.datagen import DataGenerator
from pynav.utils import GaussianResult
from pynav.models import SingleIntegrator, RangePointToAnchor
import numpy as np
from typing import List
import time

"""
This is an example script showing how to define a custom process model and
measurement model, generate data using those models, and then run an EKF 
on that data.
"""

# ##############################################################################
# Problem Setup

x0 = VectorState(np.array([1, 0]))
P0 = np.diag([1, 1])
R = 0.1**2
Q = 0.1 * np.identity(2)
range_models = [
    RangePointToAnchor([0, 4], R),
    RangePointToAnchor([-2, 0], R),
    RangePointToAnchor([2, 0], R),
]
range_freqs = [50, 50, 50]
process_model = SingleIntegrator(Q)
input_profile = lambda t: np.array([np.sin(t), np.cos(t)])
input_covariance = Q
input_freq = 200

# ##############################################################################
# Data Generation

dg = DataGenerator(
    process_model,
    input_profile,
    input_covariance,
    input_freq,
    range_models,
    range_freqs,
)

gt_data, input_data, meas_data = dg.generate(x0, 0, 10, noise=True)

# ##############################################################################
# Run Filter

ekf = ExtendedKalmanFilter(x0, P0, process_model)

meas_idx = 0
start_time = time.time()
y = meas_data[meas_idx]
results: List[GaussianResult] = []
for k in range(len(input_data) - 1):
    u = input_data[k]

    # Fuse any measurements that have occurred.
    while y.stamp < input_data[k + 1].stamp and meas_idx < len(meas_data):

        ekf.correct(y)
        meas_idx += 1
        if meas_idx < len(meas_data):
            y = meas_data[meas_idx]

    ekf.predict(u)
    results.append(GaussianResult(ekf.x, ekf.P, gt_data[k]))

print("Average filter computation frequency (Hz):")
print(1 / ((time.time() - start_time) / len(input_data)))


# ##############################################################################
# Post processing
t = np.array([r.stamp for r in results])
e = np.array([r.error for r in results])
x = np.array([r.state.value for r in results])
x_gt = np.array([r.state_gt.value for r in results])
three_sigma = np.array([r.three_sigma for r in results])

import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme()
fig, ax = plt.subplots(1, 1)
ax.plot(x[:, 0], x[:, 1], label="Estimate")
ax.plot(x_gt[:, 0], x_gt[:, 1], label="Ground truth")
ax.set_title("Trajectory")
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.legend()

fig, axs = plt.subplots(2, 1)
axs: List[plt.Axes] = axs
for i in range(len(axs)):
    axs[i].fill_between(t, three_sigma[:, i], -three_sigma[:, i], alpha=0.5)
    axs[i].plot(t, e[:, i])
axs[0].set_title("Estimation error")
axs[1].set_xlabel("Time (s)")
plt.show()
