"""
This is an example script showing how to run a batch estimator on custom 
process and measurement models.
"""

from pynav.batch import BatchEstimator
from pynav.lib.states import SE3State
from pynav.datagen import DataGenerator
from pynav.utils import GaussianResult, GaussianResultList, randvec
from pynav.lib.models import (
    BodyFrameVelocity,
    RangePoseToAnchor,
)
from pynav.utils import plot_error
import numpy as np
from typing import List
from pylie import SE3
import matplotlib.pyplot as plt

# #############################################################################
# Create the batch estimator with desired settings
estimator = BatchEstimator(solver="GN", max_iters=20)

# ##############################################################################
# Problem Setup
t_end = 4
x0 = SE3State(SE3.Exp([0, 0, 0, 0, 0, 0]), stamp=0.0)
P0 = 0.1**2 * np.identity(6)
R = 0.1**2
Q = np.diag([0.01**2, 0.01**2, 0.01**2, 0.1, 0.1, 0.1])
range_models = [
    RangePoseToAnchor([1, 0, 0], [0.17, 0.17, 0], R),
    RangePoseToAnchor([1, 0, 0], [-0.17, 0.17, 0], R),
    RangePoseToAnchor([-1, 0, 0], [0.17, 0.17, 0], R),
    RangePoseToAnchor([-1, 0, 0], [-0.17, 0.17, 0], R),
    RangePoseToAnchor([0, 2, 0], [0.17, 0.17, 0], R),
    RangePoseToAnchor([0, 2, 0], [-0.17, 0.17, 0], R),
    RangePoseToAnchor([0, 2, 2], [0.17, 0.17, 0], R),
    RangePoseToAnchor([0, 2, 2], [-0.17, 0.17, 0], R),
]

range_freqs = 20
process_model = BodyFrameVelocity(Q)
input_profile = lambda t, x: np.array(
    [np.sin(0.1 * t), np.cos(0.1 * t), np.sin(0.1 * t), 1, 0, 0]
)

input_covariance = Q
input_freq = 100
noise_active = True


# Generate data with no noise
dg = DataGenerator(
    process_model,
    input_profile,
    Q,
    input_freq,
    range_models,
    range_freqs,
)

state_true, input_list, meas_list = dg.generate(x0, 0, t_end, noise_active)

# Run batch
estimate_list, opt_results = estimator.solve(
    x0,
    P0,
    input_list,
    meas_list,
    process_model,
    return_opt_results=True,
)

print(opt_results["summary"])


results = GaussianResultList(
    [
        GaussianResult(estimate_list[i], state_true[i])
        for i in range(len(estimate_list))
    ]
)

fig, ax = plot_error(results)
ax[-1][0].set_xlabel("Time (s)")
ax[-1][1].set_xlabel("Time (s)")
ax[0][0].set_title("Orientation Error")
ax[0][1].set_title("Position Error")
plt.show()
