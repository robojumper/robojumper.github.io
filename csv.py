import numpy as np
import matplotlib.pyplot as plt

import sys

data = np.genfromtxt(sys.argv[1], delimiter=',', skip_header=1)
x, y = zip(*data)

y -= y[0]

fig = plt.figure()
fig.patch.set_facecolor('#fffffd')

ax1 = fig.add_subplot()
ax1.set_facecolor('#fffffd')
ax1.set_title('Negative performance impact of creating names')
ax1.set_xlabel('#Names created (100k)')
ax1.set_ylabel('Time (s)')
ax1.plot(x, y, label='Elapsed', color='lightblue')
leg = ax1.legend()

plt.savefig(sys.argv[2])