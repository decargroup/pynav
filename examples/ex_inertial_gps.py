from typing import List
import matplotlib.pyplot as plt
import numpy as np
from pylie import SE23
from pynav.filters import ExtendedKalmanFilter, run_filter
from pynav.lib.models import (
    InvariantMeasurement,
    GlobalPosition,
)
from pynav.lib.imu import IMU, IMUState, IMUKinematics
from pynav.utils import GaussianResult, GaussianResultList, plot_error, randvec
from pynav.datagen import DataGenerator
np.set_printoptions(precision=3, suppress=True, linewidth=200)

# ##############################################################################
# Problem Setup
np.random.seed(0)
t_start = 0
t_end = 90
imu_freq = 200
noise_active = True 

# IMU noise parameters
sigma_gyro_ct = 0.01
sigma_accel_ct = 0.01
sigma_gyro_bias_ct = 0.0001
sigma_accel_bias_ct = 0.0001
init_gyro_bias = np.array([0.02, 0.03, -0.04]).reshape((-1, 1))
init_accel_bias = np.array([0.01, 0.02, 0.05]).reshape((-1, 1))

# GPS sensor parameters
sigma_gps = 0.1  # [m]
gps_freq = 5

# Initialization parameters
sigma_phi_init = 0.1
sigma_v_init = 0.1
sigma_r_init = 0.1
sigma_bg_init = 0.01
sigma_ba_init = 0.01
nav_state_init = SE23.from_components(
    np.identity(3),
    np.array([0, 3, 3]).reshape((-1, 1)),
    np.array([3, 0, 0]).reshape((-1, 1)),
)

################################################################################
################################################################################

# Continuous-time Power Spectral Density
Q_c = np.eye(12)
Q_c[0:3, 0:3] *= sigma_gyro_ct**2
Q_c[3:6, 3:6] *= sigma_accel_ct**2
Q_c[6:9, 6:9] *= sigma_gyro_bias_ct**2
Q_c[9:12, 9:12] *= sigma_accel_bias_ct**2
dt = 1 / imu_freq

Q_noise = Q_c / dt

def input_profile(stamp: float, x: IMUState) -> np.ndarray:
    """Generates an IMU measurement for a circular trajectory,
    where the robot only rotates about the z-axis and the acceleration
    points towards the center of the circle.
    """

    # Add biases to true angular velocity and acceleration
    bias_gyro = x.bias_gyro.reshape((-1, 1))
    bias_accel = x.bias_accel.reshape((-1, 1))

    C_ab = x.attitude
    g_a = np.array([0, 0, -9.80665]).reshape((-1, 1))
    omega = np.array([0.1, 0, 0.5]).reshape((-1, 1)) + bias_gyro
    a_a = np.array([-3*np.cos(stamp), -3*np.sin(stamp),  -9*np.sin(3*stamp)]).reshape((-1, 1))
    accel = C_ab.T @ a_a  + bias_accel - C_ab.T @ g_a

    # Generate a random input to drive the bias random walk
    Q_bias = Q_noise[6:, 6:]
    bias_noise = randvec(Q_bias)

    u = IMU(omega, accel, stamp, bias_noise[0:3], bias_noise[3:6])
    return u

process_model = IMUKinematics(Q_c / dt)
meas_cov = np.identity(3) * sigma_gps**2
meas_model_list = [GlobalPosition(meas_cov)]

# Create data generator
data_gen = DataGenerator(
    process_model,
    input_func=input_profile,
    input_covariance=Q_noise,
    input_freq=imu_freq,
    meas_model_list=meas_model_list,
    meas_freq_list=gps_freq,
)

# Initial state and covariance
x0 = IMUState(
    nav_state_init,
    init_gyro_bias,
    init_accel_bias,
    stamp=t_start,
    state_id=0,
    direction="right",
)

P0 = np.eye(15)
P0[0:3, 0:3] *= sigma_phi_init**2
P0[3:6, 3:6] *= sigma_v_init**2
P0[6:9, 6:9] *= sigma_r_init**2
P0[9:12, 9:12] *= sigma_bg_init**2
P0[12:15, 12:15] *= sigma_ba_init**2

# ##############################################################################
# Generate all data
states_true, input_list, meas_list = data_gen.generate(
    x0, t_start, t_end, noise=noise_active
)

# **************** Conversion to Invariant Measurements ! *********************
#meas_list = [InvariantMeasurement(meas, "left") for meas in meas_list]
# *****************************************************************************

# Zero-out the random walk values (thus creating "noise")
if noise_active:
    for u in input_list:
        u.bias_gyro_walk = np.array([0, 0, 0])
        u.bias_accel_walk = np.array([0, 0, 0])


# ##############################################################################
# Run filter
ekf = ExtendedKalmanFilter(process_model)
x0 = x0.plus(randvec(P0))
estimate_list = run_filter(ekf, x0, P0, input_list, meas_list)

# Postprocess the results and plot
results = GaussianResultList(
    [
        GaussianResult(estimate_list[i], states_true[i])
        for i in range(len(estimate_list))
    ]
)


# ##############################################################################
# Plot results
from pynav.utils import plot_poses
import seaborn as sns

fig = plt.figure()
ax = plt.axes(projection="3d")
states_list = [x.state for x in estimate_list]
plot_poses(states_list, ax, line_color="tab:blue", step=20, label="Estimate")
plot_poses(states_true, ax, line_color="tab:red", step=500, label="Groundtruth")
ax.legend()

sns.set_theme()
fig, axs = plot_error(results)
axs[0, 0].set_title("Attitude")
axs[0, 1].set_title("Velocity")
axs[0, 2].set_title("Position")
axs[0, 3].set_title("Gyro bias")
axs[0, 4].set_title("Accel bias")
axs[-1, 2]

plt.show()
