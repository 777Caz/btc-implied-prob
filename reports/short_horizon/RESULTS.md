# Short-horizon scaling of the 08:00 UTC front smile (generated 2026-10-03 09:57 UTC)

Days with a forecast: 1869 (common sample, all variants), 2021-06-24 to 2026-08-29; event days: 162.
Fit status by day: {'ok': 1952, 'no front fit': 24}

## Scores: all days
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5  1869         0.9717 0.1065    0.0487 0.040-0.059     0.0562 0.047-0.068         0.5227            3                 0           2.8005                2.5933           -0.0062               0.0029
17:00 NY    vartime+events, a=0.5  1869         0.9230 0.0600    0.0417 0.034-0.052     0.0455 0.037-0.056         0.5350            3                 0           2.7652                2.5993           -0.0002               0.0004
17:00 NY vartime+events, a=fitted  1869         0.9224 0.0600    0.0417 0.034-0.052     0.0455 0.037-0.056         0.5350            3                 0           2.7621                2.5991           -0.0005               0.0004
17:00 NY           vartime, a=0.5  1869         0.9274 0.0600    0.0423 0.034-0.052     0.0465 0.038-0.057         0.5345            3                 0           2.7723                2.5996            0.0000               0.0000
17:00 NY        vartime, a=fitted  1869         0.9268 0.0600    0.0423 0.034-0.052     0.0465 0.038-0.057         0.5345            3                 0           2.7667                2.5994           -0.0002               0.0001
 noon NY             clock, a=0.5  1869         0.9771 0.1162    0.0471 0.038-0.058     0.0572 0.048-0.069         0.5131            3                 1           3.0253                2.8305           -0.0102               0.0033
 noon NY    vartime+events, a=0.5  1869         0.9488 0.0639    0.0412 0.033-0.051     0.0546 0.045-0.066         0.5243            2                 1           2.9896                2.8425            0.0018               0.0011
 noon NY vartime+events, a=fitted  1869         0.9475 0.0568    0.0412 0.033-0.051     0.0546 0.045-0.066         0.5254            2                 1           2.9896                2.8421            0.0014               0.0011
 noon NY           vartime, a=0.5  1869         0.9496 0.0639    0.0423 0.034-0.052     0.0551 0.046-0.066         0.5211            2                 1           2.9922                2.8407            0.0000               0.0000
 noon NY        vartime, a=fitted  1869         0.9484 0.0568    0.0423 0.034-0.052     0.0551 0.046-0.066         0.5222            2                 1           2.9909                2.8403           -0.0004               0.0002
```

## Scores: excluding event days
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5  1707         0.9610 0.0847    0.0486 0.039-0.060     0.0557 0.046-0.068         0.5290            3                 0           2.8318                2.6180           -0.0070               0.0031
17:00 NY    vartime+events, a=0.5  1707         0.9212 0.0432    0.0428 0.034-0.053     0.0469 0.038-0.058         0.5401            3                 0           2.7935                2.6250            0.0000               0.0000
17:00 NY vartime+events, a=fitted  1707         0.9206 0.0406    0.0428 0.034-0.053     0.0469 0.038-0.058         0.5401            3                 0           2.7914                2.6247           -0.0002               0.0001
17:00 NY           vartime, a=0.5  1707         0.9212 0.0432    0.0428 0.034-0.053     0.0469 0.038-0.058         0.5401            3                 0           2.7935                2.6250            0.0000               0.0000
17:00 NY        vartime, a=fitted  1707         0.9206 0.0406    0.0428 0.034-0.053     0.0469 0.038-0.058         0.5401            3                 0           2.7914                2.6247           -0.0002               0.0001
 noon NY             clock, a=0.5  1707         0.9667 0.0347    0.0475 0.038-0.059     0.0551 0.045-0.067         0.5214            3                 1           3.0530                2.8572           -0.0105               0.0035
 noon NY    vartime+events, a=0.5  1707         0.9454 0.0216    0.0428 0.034-0.053     0.0533 0.044-0.065         0.5261            2                 1           3.0167                2.8677            0.0000               0.0000
 noon NY vartime+events, a=fitted  1707         0.9442 0.0190    0.0428 0.034-0.053     0.0533 0.044-0.065         0.5272            2                 1           3.0165                2.8672           -0.0004               0.0002
 noon NY           vartime, a=0.5  1707         0.9454 0.0216    0.0428 0.034-0.053     0.0533 0.044-0.065         0.5261            2                 1           3.0167                2.8677            0.0000               0.0000
 noon NY        vartime, a=fitted  1707         0.9442 0.0190    0.0428 0.034-0.053     0.0533 0.044-0.065         0.5272            2                 1           3.0165                2.8672           -0.0004               0.0002
```

## Scores: event days only
```
  target                  variant  days  pit_var_ratio   ks_p  below_5%    below_ci  above_95%    above_ci  inside_25_75%  tail_misses  logscore_floored  median_logscore  mean_logscore_capped  logscore_vs_base  logscore_vs_base_se
17:00 NY             clock, a=0.5   162         1.0866 0.3789    0.0494 0.025-0.094     0.0617 0.034-0.110         0.4568            0                 0           2.5673                2.3337            0.0016               0.0082
17:00 NY    vartime+events, a=0.5   162         0.9436 0.7230    0.0309 0.013-0.070     0.0309 0.013-0.070         0.4815            0                 0           2.5020                2.3293           -0.0029               0.0050
17:00 NY vartime+events, a=fitted   162         0.9432 0.7095    0.0309 0.013-0.070     0.0309 0.013-0.070         0.4815            0                 0           2.5018                2.3293           -0.0028               0.0050
17:00 NY           vartime, a=0.5   162         0.9948 0.8305    0.0370 0.017-0.078     0.0432 0.021-0.086         0.4753            0                 0           2.5129                2.3322            0.0000               0.0000
17:00 NY        vartime, a=fitted   162         0.9944 0.8072    0.0370 0.017-0.078     0.0432 0.021-0.086         0.4753            0                 0           2.5116                2.3322            0.0000               0.0002
 noon NY             clock, a=0.5   162         1.0614 0.0939    0.0432 0.021-0.086     0.0802 0.047-0.132         0.4259            0                 0           2.8179                2.5500           -0.0066               0.0091
 noon NY    vartime+events, a=0.5   162         0.9613 0.2464    0.0247 0.010-0.062     0.0679 0.038-0.117         0.5062            0                 0           2.7404                2.5770            0.0203               0.0126
 noon NY vartime+events, a=fitted   162         0.9600 0.2464    0.0247 0.010-0.062     0.0679 0.038-0.117         0.5062            0                 0           2.7404                2.5771            0.0205               0.0125
 noon NY           vartime, a=0.5   162         0.9709 0.2590    0.0370 0.017-0.078     0.0741 0.043-0.125         0.4691            0                 0           2.7743                2.5566            0.0000               0.0000
 noon NY        vartime, a=fitted   162         0.9697 0.2590    0.0370 0.017-0.078     0.0741 0.043-0.125         0.4691            0                 0           2.7671                2.5566            0.0000               0.0003
```

## Mean lambda (fraction of the front expiry's variance used)
```
variant   clock, a=0.5  vartime+events, a=0.5  vartime, a=0.5
target                                                       
17:00 NY        0.5556                 0.6183          0.6124
noon NY         0.3472                 0.3762          0.3738
```

## alpha: daily fits from ~1-day vs ~1-week smiles, and the expanding median used
```
       alpha_day_fit  alpha_used
count      1382.0000   1869.0000
mean          0.4972      0.4896
std           0.0771      0.0201
min           0.0000      0.4500
25%           0.4500      0.5000
50%           0.5000      0.5000
75%           0.5500      0.5000
max           0.7500      0.5000
```

## Arbitrage checks on every scaled smile (g < -1e-4 = butterfly; w_s > w1 = calendar)
```
                          forecasts  butterfly_violations  calendar_violations  worst_g  worst_calendar
variant                                                                                                
clock, a=0.5                   3904                    18                    4  -0.0287          0.2164
vartime+events, a=0.5          3904                    18                    4  -0.0287          0.2116
vartime+events, a=fitted       3738                    14                    2  -0.0287          0.2116
vartime, a=0.5                 3904                    18                    4  -0.0287          0.2116
vartime, a=fitted              3738                    14                    2  -0.0287          0.2116
```
Front smiles that themselves have butterfly g < -1e-4: 12 of 1976 days.

### Calendar violations by |SVI centre m| in front standard deviations (vartime, a=0.5)
Excess is max(w_s - w1) relative to the front's ATM total variance.
```
                forecasts  violation_rate  median_excess_if_violated
m_in_sd                                                             
(-0.001, 0.25]        506          0.0000                        NaN
(0.25, 0.5]           508          0.0000                        NaN
(0.5, 1.0]           1720          0.0012                     0.1161
(1.0, 2.0]           1170          0.0017                     0.2115
```

## Event excess (full sample, descriptive; forecasts use earlier events only)
```
event  events  extra_variance_day_units  share_by_+5min  share_by_+30min  share_by_+60min  first_5min_vs_normal_x
  CPI      64                    0.2623          0.6461           0.8026           0.8443                 10.8939
  NFP      64                    0.1411          0.5339           0.7759           0.8054                  7.7709
 FOMC      43                    0.6184          0.4231           0.5484           0.7963                 28.9866
```

## Constraining the front SVI centre m (|m| <= 1 ATM SD and within traded strikes): before vs after

### Front fit error (trade-weighted RMSE, vol points), same days
```
                                               unconstrained m  constrained m
count                                                1929.0000      1929.0000
mean                                                    1.8882         1.9770
50%                                                     1.6148         1.6726
90%                                                     3.0952         3.2616
share of days with |m| > 1 SD (unconstrained)           0.6594            NaN
```
### Arbitrage checks
```
                            before                                                             after                                                        
                         forecasts butterfly_violations calendar_violations worst_calendar forecasts butterfly_violations calendar_violations worst_calendar
variant                                                                                                                                                     
clock, a=0.5                  3858                  168                 228         6.5518      3904                   18                   4         0.2164
vartime+events, a=0.5         3858                  168                 261         6.5562      3904                   18                   4         0.2116
vartime+events, a=fitted      3692                   75                 179         6.5562      3738                   14                   2         0.2116
vartime, a=0.5                3858                  168                 262         6.5562      3904                   18                   4         0.2116
vartime, a=fitted             3692                   75                 180         6.5562      3738                   14                   2         0.2116
```
### Scores, all days
```
                                  before                                                                                                      after                                                                                                     
                                    days pit_var_ratio below_5% above_95% inside_25_75% median_logscore mean_logscore_capped logscore_vs_base  days pit_var_ratio below_5% above_95% inside_25_75% median_logscore mean_logscore_capped logscore_vs_base
target   variant                                                                                                                                                                                                                                        
17:00 NY clock, a=0.5               1846        0.9639   0.0477    0.0525        0.5265          2.7917               2.5927           0.0005  1869        0.9717   0.0487    0.0562        0.5227          2.8005               2.5933          -0.0062
         vartime+events, a=0.5      1846        0.9158   0.0423    0.0455        0.5390          2.7623               2.5920          -0.0002  1869        0.9230   0.0417    0.0455        0.5350          2.7652               2.5993          -0.0002
         vartime+events, a=fitted   1846        0.9151   0.0423    0.0455        0.5390          2.7605               2.5920          -0.0002  1869        0.9224   0.0417    0.0455        0.5350          2.7621               2.5991          -0.0005
         vartime, a=0.5             1846        0.9202   0.0428    0.0466        0.5374          2.7660               2.5922           0.0000  1869        0.9274   0.0423    0.0465        0.5345          2.7723               2.5996           0.0000
         vartime, a=fitted          1846        0.9195   0.0428    0.0466        0.5374          2.7632               2.5923           0.0000  1869        0.9268   0.0423    0.0465        0.5345          2.7667               2.5994          -0.0002
noon NY  clock, a=0.5               1846        0.9678   0.0477    0.0563        0.5152          3.0194               2.8362          -0.0089  1869        0.9771   0.0471    0.0572        0.5131          3.0253               2.8305          -0.0102
         vartime+events, a=0.5      1846        0.9402   0.0412    0.0547        0.5303          2.9859               2.8470           0.0019  1869        0.9488   0.0412    0.0546        0.5243          2.9896               2.8425           0.0018
         vartime+events, a=fitted   1846        0.9388   0.0412    0.0547        0.5336          2.9820               2.8471           0.0020  1869        0.9475   0.0412    0.0546        0.5254          2.9896               2.8421           0.0014
         vartime, a=0.5             1846        0.9409   0.0428    0.0553        0.5265          2.9859               2.8451           0.0000  1869        0.9496   0.0423    0.0551        0.5211          2.9922               2.8407           0.0000
         vartime, a=fitted          1846        0.9395   0.0428    0.0553        0.5298          2.9829               2.8452           0.0001  1869        0.9484   0.0423    0.0551        0.5222          2.9909               2.8403          -0.0004
```
### Paired change in capped log score (after - before), same days
```
                                   logscore_after_minus_before     se  paired_days
target   variant                                                                  
17:00 NY clock, a=0.5                                   0.0036 0.0046         1929
         vartime+events, a=0.5                          0.0102 0.0064         1929
         vartime+events, a=fitted                       0.0103 0.0067         1846
         vartime, a=0.5                                 0.0102 0.0064         1929
         vartime, a=fitted                              0.0104 0.0067         1846
noon NY  clock, a=0.5                                  -0.0011 0.0049         1929
         vartime+events, a=0.5                         -0.0004 0.0040         1929
         vartime+events, a=fitted                      -0.0012 0.0041         1846
         vartime, a=0.5                                -0.0003 0.0040         1929
         vartime, a=fitted                             -0.0011 0.0041         1846
```
