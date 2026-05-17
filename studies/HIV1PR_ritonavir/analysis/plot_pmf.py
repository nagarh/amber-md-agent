"""Plot the PMF from WHAM output."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

data = np.loadtxt('pmf.dat', comments='#')
xi, pmf = data[:,0], data[:,1]

fig, ax = plt.subplots(figsize=(8,5))
ax.plot(xi, pmf, 'b-', linewidth=2)
ax.fill_between(xi, pmf, alpha=0.15, color='blue')
ax.set_xlabel('COM Distance (Å)', fontsize=13)
ax.set_ylabel('PMF (kcal/mol)', fontsize=13)
ax.set_title('Ritonavir Unbinding PMF — HIV-1 Protease', fontsize=14)
ax.axvline(x=xi[np.argmax(pmf)], color='r', linestyle='--', alpha=0.7,
           label=f'Barrier at {xi[np.argmax(pmf)]:.1f} Å')
ax.axhline(y=max(pmf), color='r', linestyle=':', alpha=0.5,
           label=f'ΔG = {max(pmf):.1f} kcal/mol')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('pmf.png', dpi=150)
print(f"PMF plot saved: pmf.png")
print(f"Barrier height: {max(pmf):.2f} kcal/mol")
