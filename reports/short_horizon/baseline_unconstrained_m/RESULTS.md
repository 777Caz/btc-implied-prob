# Short-horizon scaling of the 08:00 UTC front smile (generated 2026-10-03 00:25 UTC)

Days with a forecast: 1846 (common sample, all variants), 2021-06-24 to 2026-08-29; event days: 160.
Fit status by day: {'ok': 1929, 'no front fit': 47}

## Scores: all days
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5  1846         0.9639 0.1300    0.0477 0.039-0.058     0.0525 0.043-0.064         0.5265            5                 1           2.7917                2.5927            0.0005               0.0049
17:00 NY    vartime+events, a=0.5  1846         0.9158 0.0489    0.0423 0.034-0.052     0.0455 0.037-0.056         0.5390            5                 3           2.7623                2.5920           -0.0002               0.0004
17:00 NY vartime+events, a=fitted  1846         0.9151 0.0489    0.0423 0.034-0.052     0.0455 0.037-0.056         0.5390            5                 3           2.7605                2.5920           -0.0002               0.0005
17:00 NY           vartime, a=0.5  1846         0.9202 0.0489    0.0428 0.034-0.053     0.0466 0.038-0.057         0.5374            5                 3           2.7660                2.5922            0.0000               0.0000
17:00 NY        vartime, a=fitted  1846         0.9195 0.0489    0.0428 0.034-0.053     0.0466 0.038-0.057         0.5374            5                 3           2.7632                2.5923            0.0000               0.0003
 noon NY             clock, a=0.5  1846         0.9678 0.1013    0.0477 0.039-0.058     0.0563 0.047-0.068         0.5152            5                 0           3.0194                2.8362           -0.0089               0.0037
 noon NY    vartime+events, a=0.5  1846         0.9402 0.0442    0.0412 0.033-0.051     0.0547 0.045-0.066         0.5303            4                 0           2.9859                2.8470            0.0019               0.0011
 noon NY vartime+events, a=fitted  1846         0.9388 0.0442    0.0412 0.033-0.051     0.0547 0.045-0.066         0.5336            4                 0           2.9820                2.8471            0.0020               0.0013
 noon NY           vartime, a=0.5  1846         0.9409 0.0388    0.0428 0.034-0.053     0.0553 0.046-0.067         0.5265            4                 0           2.9859                2.8451            0.0000               0.0000
 noon NY        vartime, a=fitted  1846         0.9395 0.0388    0.0428 0.034-0.053     0.0553 0.046-0.067         0.5298            4                 0           2.9829                2.8452            0.0001               0.0006
```

## Scores: excluding event days
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5  1686         0.9528 0.1035    0.0474 0.038-0.059     0.0516 0.042-0.063         0.5320            5                 1           2.8222                2.6177            0.0004               0.0053
17:00 NY    vartime+events, a=0.5  1686         0.9136 0.0397    0.0433 0.035-0.054     0.0469 0.038-0.058         0.5427            5                 3           2.7841                2.6173            0.0000               0.0000
17:00 NY vartime+events, a=fitted  1686         0.9129 0.0397    0.0433 0.035-0.054     0.0469 0.038-0.058         0.5427            5                 3           2.7835                2.6173            0.0000               0.0003
17:00 NY           vartime, a=0.5  1686         0.9136 0.0397    0.0433 0.035-0.054     0.0469 0.038-0.058         0.5427            5                 3           2.7841                2.6173            0.0000               0.0000
17:00 NY        vartime, a=fitted  1686         0.9129 0.0397    0.0433 0.035-0.054     0.0469 0.038-0.058         0.5427            5                 3           2.7835                2.6173            0.0000               0.0003
 noon NY             clock, a=0.5  1686         0.9572 0.0336    0.0480 0.039-0.059     0.0540 0.044-0.066         0.5237            5                 0           3.0459                2.8635           -0.0091               0.0040
 noon NY    vartime+events, a=0.5  1686         0.9365 0.0148    0.0427 0.034-0.053     0.0534 0.044-0.065         0.5320            4                 0           3.0089                2.8726            0.0000               0.0000
 noon NY vartime+events, a=fitted  1686         0.9351 0.0148    0.0427 0.034-0.053     0.0534 0.044-0.065         0.5356            4                 0           3.0058                2.8727            0.0002               0.0007
 noon NY           vartime, a=0.5  1686         0.9365 0.0148    0.0427 0.034-0.053     0.0534 0.044-0.065         0.5320            4                 0           3.0089                2.8726            0.0000               0.0000
 noon NY        vartime, a=fitted  1686         0.9351 0.0148    0.0427 0.034-0.053     0.0534 0.044-0.065         0.5356            4                 0           3.0058                2.8727            0.0002               0.0007
```

## Scores: event days only
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5   160         1.0851 0.4388    0.0500 0.026-0.096     0.0625 0.034-0.111         0.4688            0                 0           2.5609                2.3291            0.0007               0.0085
17:00 NY    vartime+events, a=0.5   160         0.9426 0.7929    0.0312 0.013-0.071     0.0312 0.013-0.071         0.5000            0                 0           2.4943                2.3259           -0.0025               0.0052
17:00 NY vartime+events, a=fitted   160         0.9421 0.7838    0.0312 0.013-0.071     0.0312 0.013-0.071         0.5000            0                 0           2.4943                2.3259           -0.0025               0.0052
17:00 NY           vartime, a=0.5   160         0.9939 0.7929    0.0375 0.017-0.079     0.0437 0.021-0.088         0.4813            0                 0           2.5048                2.3284            0.0000               0.0000
17:00 NY        vartime, a=fitted   160         0.9934 0.7838    0.0375 0.017-0.079     0.0437 0.021-0.088         0.4813            0                 0           2.5034                2.3284           -0.0000               0.0002
 noon NY             clock, a=0.5   160         1.0588 0.1103    0.0437 0.021-0.088     0.0813 0.048-0.134         0.4250            0                 0           2.8153                2.5487           -0.0066               0.0093
 noon NY    vartime+events, a=0.5   160         0.9603 0.3436    0.0250 0.010-0.063     0.0688 0.039-0.119         0.5125            0                 0           2.7354                2.5772            0.0219               0.0128
 noon NY vartime+events, a=fitted   160         0.9590 0.3436    0.0250 0.010-0.063     0.0688 0.039-0.119         0.5125            0                 0           2.7264                2.5772            0.0220               0.0128
 noon NY           vartime, a=0.5   160         0.9691 0.3102    0.0437 0.021-0.088     0.0750 0.043-0.127         0.4688            0                 0           2.7581                2.5552            0.0000               0.0000
 noon NY        vartime, a=fitted   160         0.9678 0.2905    0.0437 0.021-0.088     0.0750 0.043-0.127         0.4688            0                 0           2.7553                2.5551           -0.0001               0.0004
```

## Mean lambda (fraction of the front expiry's variance used)
```
variant   clock, a=0.5  vartime+events, a=0.5  vartime, a=0.5
target                                                       
17:00 NY        0.5556                 0.6178          0.6119
noon NY         0.3472                 0.3758          0.3735
```

## alpha: daily fits from ~1-day vs ~1-week smiles, and the expanding median used
```
       alpha_day_fit  alpha_used
count      1367.0000   1846.0000
mean          0.4952      0.4873
std           0.0795      0.0217
min           0.0000      0.4500
25%           0.4500      0.4500
50%           0.5000      0.5000
75%           0.5500      0.5000
max           0.7500      0.5000
```

## Arbitrage checks on every scaled smile (g < -1e-4 = butterfly; w_s > w1 = calendar)
```
                          forecasts  butterfly_violations  calendar_violations  worst_g  worst_calendar
variant                                                                                                
clock, a=0.5                   3858                   168                  228  -0.0321          6.5518
vartime+events, a=0.5          3858                   168                  261  -0.0321          6.5562
vartime+events, a=fitted       3692                    75                  179  -0.0321          6.5562
vartime, a=0.5                 3858                   168                  262  -0.0321          6.5562
vartime, a=fitted              3692                    75                  180  -0.0321          6.5562
```
Front smiles that themselves have butterfly g < -1e-4: 167 of 1976 days.

### Calendar violations by |SVI centre m| in front standard deviations (vartime, a=0.5)
Excess is max(w_s - w1) relative to the front's ATM total variance.
```
                forecasts  violation_rate  median_excess_if_violated
m_in_sd                                                             
(-0.001, 0.25]        362          0.0000                        NaN
(0.25, 0.5]           346          0.0000                        NaN
(0.5, 1.0]            606          0.0000                        NaN
(1.0, 2.0]            686          0.0000                        NaN
(2.0, inf]           1858          0.1410                     0.1565
```

## Event excess (full sample, descriptive; forecasts use earlier events only)
```
event  events  extra_variance_day_units  share_by_+5min  share_by_+30min  share_by_+60min  first_5min_vs_normal_x
  CPI      64                    0.2623          0.6461           0.8026           0.8443                 10.8939
  NFP      64                    0.1411          0.5339           0.7759           0.8054                  7.7709
 FOMC      43                    0.6184          0.4231           0.5484           0.7963                 28.9866
```