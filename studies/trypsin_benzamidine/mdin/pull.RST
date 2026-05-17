# SMD pull: BEN COM <-> ASP189 CA, r2 from 3.0 -> 17.0 A over nstlim
# Group 1 = BEN heavy atoms (3222-3230); Group 2 = Asp189 CA (2467)
 &rst
   iat=-1, -1,
   r1=0.0, r2=3.0, rk2=50.0, rk3=50.0,
   r2a=17.0,
   igr1=3222,3223,3224,3225,3226,3227,3228,3229,3230,0,
   igr2=2467,0,
 /
