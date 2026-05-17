#!/usr/bin/env python3
import parmed as pmd, os

STUDY = 'studies/HSP90_radicicol'
SYSDIR = f'{STUDY}/system'
ANADIR = f'{STUDY}/analysis'

com = pmd.load_file(f'{SYSDIR}/system.prmtop', f'{SYSDIR}/system.inpcrd')

# complex stripped
com_strip = pmd.load_file(f'{SYSDIR}/system.prmtop', f'{SYSDIR}/system.inpcrd')
com_strip.strip(':WAT,Na+,Cl-')
com_strip.box = None
com_strip.save(f'{ANADIR}/complex.prmtop', overwrite=True)
print(f'complex: {len(com_strip.atoms)} atoms')

# receptor (protein only)
rec = pmd.load_file(f'{SYSDIR}/system.prmtop', f'{SYSDIR}/system.inpcrd')
rec.strip(':WAT,Na+,Cl-,MOL')
rec.box = None
rec.save(f'{ANADIR}/receptor.prmtop', overwrite=True)
print(f'receptor: {len(rec.atoms)} atoms')

# ligand only
lig = pmd.load_file(f'{SYSDIR}/system.prmtop', f'{SYSDIR}/system.inpcrd')
lig.strip('!:MOL')
lig.box = None
lig.save(f'{ANADIR}/ligand.prmtop', overwrite=True)
print(f'ligand: {len(lig.atoms)} atoms')

print('Done — all 3 stripped prmtops written')
