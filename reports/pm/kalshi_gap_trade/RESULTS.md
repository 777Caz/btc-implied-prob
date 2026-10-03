# Gap-conditional trade test, Kalshi 17:00 NY at 08:00 UTC vs option q (generated 2026-10-03 21:25 UTC)

Rules fixed in advance; thresholds T = 2c, 3c, 5c; no tuning on 2026. 100 contracts per trade, held to settlement.
P&L in cents per contract after fees; CI = 95% cluster bootstrap by event (one event per day). Drawdown on cumulative daily P&L.

## Both sides
```
                           q_source                             style   T_c   period  trades  days_traded  days_available  yes_share  mean_price_c  mean_edge_c  hit_rate  pnl_per_contract_c  ci_lo  ci_hi  total_usd_100_contracts  max_drawdown_usd  days_positive_share
              q (8h smile, primary)                             taker 2.000 pre-2026     515          171             491      0.408        71.876        7.191     0.767               3.814 -1.868  9.031                 1964.070          -820.250                0.725
              q (8h smile, primary)                             taker 2.000     2026     890          180             265      0.519        74.224        5.871     0.762               0.902 -2.515  4.287                  802.500         -1693.510                0.661
              q (8h smile, primary)                             taker 3.000 pre-2026     341          130             491      0.378        68.686        9.181     0.754               5.586 -1.483 11.649                 1904.930          -690.900                0.715
              q (8h smile, primary)                             taker 3.000     2026     573          135             265      0.536        71.653        7.281     0.745               1.714 -2.857  6.039                  982.270         -1362.190                0.659
              q (8h smile, primary)                             taker 5.000 pre-2026     156           59             491      0.321        65.019       14.414     0.808              14.444  4.264 21.540                 2253.330          -185.700                0.814
              q (8h smile, primary)                             taker 5.000     2026     255           65             265      0.475        67.780       10.314     0.722               3.084 -4.051 10.289                  786.470         -1147.730                0.615
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026    2819          252             491      0.659        63.164        5.735     0.672               3.987  1.638  6.310                11240.000         -2393.000                0.651
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000     2026    3623          265             265      0.515        75.806        4.519     0.792               3.382  1.663  5.048                12254.000         -2139.000                0.668
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026    2583          251             491      0.578        65.809        6.247     0.704               4.613  2.473  6.684                11916.000         -2126.000                0.665
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000     2026    2319          256             265      0.529        73.531        5.686     0.772               3.658  1.402  5.835                 8482.000         -2081.000                0.648
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026    1643          238             491      0.500        68.834        7.600     0.736               4.812  1.831  7.710                 7906.000         -1944.000                0.641
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000     2026    1029          192             265      0.551        71.142        7.950     0.766               5.437  2.202  8.672                 5595.000         -1135.000                0.656
q_1h (last-hour smile, sensitivity)                             taker 2.000 pre-2026     468          168             491      0.391        70.175        7.328     0.726               1.427 -5.012  7.912                  667.610          -915.860                0.708
q_1h (last-hour smile, sensitivity)                             taker 2.000     2026     755          178             261      0.514        72.254        5.338     0.750               1.603 -2.734  5.699                 1210.250         -1943.660                0.663
q_1h (last-hour smile, sensitivity)                             taker 3.000 pre-2026     314          125             491      0.376        67.398        9.305     0.729               4.400 -2.966 11.624                 1381.710          -550.140                0.720
q_1h (last-hour smile, sensitivity)                             taker 3.000     2026     446          133             261      0.500        69.518        6.674     0.717               1.007 -4.504  6.319                  449.300         -1920.740                0.647
q_1h (last-hour smile, sensitivity)                             taker 5.000 pre-2026     151           64             491      0.338        61.046       14.195     0.748              12.489  1.756 20.342                 1885.790          -167.650                0.781
q_1h (last-hour smile, sensitivity)                             taker 5.000     2026     181           56             261      0.486        65.387        9.156     0.718               5.085 -2.901 13.342                  920.440          -735.940                0.607
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026    2819          253             491      0.645        64.225        5.767     0.674               3.210  0.908  5.406                 9050.000         -1896.000                0.656
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000     2026    3405          261             261      0.507        73.293        4.333     0.773               4.005  2.127  5.863                13637.000         -1661.000                0.651
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026    2611          251             491      0.582        67.020        6.211     0.704               3.412  1.045  5.748                 8910.000         -2345.000                0.653
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000     2026    2171          256             261      0.539        71.440        5.397     0.762               4.746  2.363  7.120                10304.000         -1888.000                0.648
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026    1696          240             491      0.508        69.259        7.465     0.740               4.739  1.907  7.564                 8037.000         -1571.000                0.625
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000     2026     901          186             261      0.559        68.425        7.532     0.727               4.272  0.224  8.084                 3849.000         -1895.000                0.634
```
## By side
```
                           q_source                             style   T_c   period side  trades  days_traded  days_available  yes_share  mean_price_c  mean_edge_c  hit_rate  pnl_per_contract_c   ci_lo  ci_hi  total_usd_100_contracts  max_drawdown_usd  days_positive_share
              q (8h smile, primary)                             taker 2.000 pre-2026  YES     210           90             491      1.000        75.695        7.533     0.800               3.364  -5.372 11.198                  706.440          -654.790                0.756
              q (8h smile, primary)                             taker 2.000 pre-2026   NO     305          123             491      0.000        69.246        6.955     0.744               4.123  -2.897 10.581                 1257.630          -617.530                0.756
              q (8h smile, primary)                             taker 2.000     2026  YES     462          125             265      1.000        70.613        5.692     0.758               3.988  -1.830  9.169                 1842.430         -1133.230                0.720
              q (8h smile, primary)                             taker 2.000     2026   NO     428          127             265      0.000        78.121        6.065     0.766              -2.430  -8.499  3.452                -1039.930         -1764.620                0.701
              q (8h smile, primary)                             taker 3.000 pre-2026  YES     129           57             491      1.000        72.093       10.206     0.783               5.172  -6.273 14.485                  667.240          -289.730                0.737
              q (8h smile, primary)                             taker 3.000 pre-2026   NO     212           96             491      0.000        66.613        8.557     0.736               5.838  -1.440 12.745                 1237.690          -459.660                0.740
              q (8h smile, primary)                             taker 3.000     2026  YES     307           91             265      1.000        68.511        6.811     0.759               6.155  -0.362 12.239                 1889.710          -795.280                0.736
              q (8h smile, primary)                             taker 3.000     2026   NO     266           92             265      0.000        75.278        7.825     0.729              -3.411 -11.238  4.413                 -907.440         -1501.890                0.674
              q (8h smile, primary)                             taker 5.000 pre-2026  YES      50           15             491      1.000        68.160       19.029     0.900              20.482   6.914 26.908                 1024.080           -89.690                0.933
              q (8h smile, primary)                             taker 5.000 pre-2026   NO     106           49             491      0.000        63.538       12.237     0.764              11.597   1.232 20.547                 1229.250          -185.700                0.796
              q (8h smile, primary)                             taker 5.000     2026  YES     121           41             265      1.000        63.620        9.663     0.736               8.554  -3.485 17.548                 1034.980          -554.590                0.659
              q (8h smile, primary)                             taker 5.000     2026   NO     134           38             265      0.000        71.537       10.901     0.709              -1.855 -14.042 10.886                 -248.510          -918.590                0.658
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026  YES    1857          240             491      1.000        59.235        5.206     0.624               3.124  -0.438  6.824                 5801.000         -2972.000                0.646
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026   NO     962          216             491      0.000        70.749        6.757     0.764               5.654   0.956  9.980                 5439.000         -1090.000                0.699
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000     2026  YES    1866          256             265      1.000        73.495        4.531     0.774               3.890   0.650  6.856                 7259.000         -2958.000                0.691
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 2.000     2026   NO    1757          253             265      0.000        78.261        4.506     0.811               2.843  -0.000  5.630                 4995.000         -1476.000                0.731
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026  YES    1492          238             491      1.000        63.480        5.861     0.674               3.946   0.027  7.447                 5888.000         -2653.000                0.684
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026   NO    1091          234             491      0.000        68.994        6.774     0.745               5.525   1.315  9.527                 6028.000         -1290.000                0.688
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000     2026  YES    1227          232             265      1.000        71.622        5.609     0.764               4.743   0.874  8.254                 5820.000         -2289.000                0.707
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 3.000     2026   NO    1092          214             265      0.000        75.676        5.772     0.781               2.438  -1.340  6.207                 2662.000         -1532.000                0.715
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026  YES     822          208             491      1.000        68.010        7.401     0.724               4.375  -0.582  9.176                 3596.000         -1724.000                0.688
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026   NO     821          199             491      0.000        69.659        7.800     0.749               5.250   0.290 10.007                 4310.000          -910.000                0.678
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000     2026  YES     567          156             265      1.000        69.048        7.598     0.769               7.848   2.299 12.418                 4450.000          -804.000                0.718
              q (8h smile, primary) maker (OPTIMISTIC: assumes fills) 5.000     2026   NO     462          137             265      0.000        73.712        8.383     0.762               2.478  -3.499  8.359                 1145.000         -1329.000                0.708
q_1h (last-hour smile, sensitivity)                             taker 2.000 pre-2026  YES     183           83             491      1.000        72.186        7.887     0.770               3.899  -5.801 11.819                  713.530          -500.990                0.747
q_1h (last-hour smile, sensitivity)                             taker 2.000 pre-2026   NO     285          120             491      0.000        68.884        6.968     0.698              -0.161  -8.681  8.081                  -45.920         -1014.990                0.742
q_1h (last-hour smile, sensitivity)                             taker 2.000     2026  YES     388          125             261      1.000        67.758        5.301     0.719               2.932  -3.477  8.527                 1137.800         -1317.900                0.688
q_1h (last-hour smile, sensitivity)                             taker 2.000     2026   NO     367          117             261      0.000        77.008        5.376     0.782               0.197  -6.159  6.192                   72.450         -1161.120                0.761
q_1h (last-hour smile, sensitivity)                             taker 3.000 pre-2026  YES     118           56             491      1.000        68.966       10.457     0.763               6.241  -5.639 15.265                  736.390          -383.920                0.732
q_1h (last-hour smile, sensitivity)                             taker 3.000 pre-2026   NO     196           91             491      0.000        66.454        8.611     0.709               3.292  -6.266 11.606                  645.320          -509.810                0.747
q_1h (last-hour smile, sensitivity)                             taker 3.000     2026  YES     223           83             261      1.000        64.457        6.584     0.682               2.402  -6.193  9.953                  535.730         -1214.780                0.675
q_1h (last-hour smile, sensitivity)                             taker 3.000     2026   NO     223           77             261      0.000        74.578        6.764     0.753              -0.388  -8.497  7.376                  -86.430         -1167.900                0.740
q_1h (last-hour smile, sensitivity)                             taker 5.000 pre-2026  YES      51           19             491      1.000        60.706       18.202     0.824              20.325   9.432 26.230                 1036.600           -22.300                0.842
q_1h (last-hour smile, sensitivity)                             taker 5.000 pre-2026   NO     100           49             491      0.000        61.220       12.151     0.710               8.492  -1.842 17.525                  849.190          -167.650                0.735
q_1h (last-hour smile, sensitivity)                             taker 5.000     2026  YES      88           34             261      1.000        59.761        8.889     0.648               3.577 -10.270 15.035                  314.770          -719.310                0.559
q_1h (last-hour smile, sensitivity)                             taker 5.000     2026   NO      93           27             261      0.000        70.710        9.408     0.785               6.513  -3.096 16.730                  605.670          -336.470                0.741
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026  YES    1819          242             491      1.000        60.371        5.279     0.629               2.576  -1.113  6.132                 4686.000         -2829.000                0.653
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000 pre-2026   NO    1000          219             491      0.000        71.236        6.654     0.756               4.364  -0.284  8.789                 4364.000          -988.000                0.699
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000     2026  YES    1725          251             261      1.000        70.813        4.430     0.750               4.144   0.931  7.335                 7148.000         -2370.000                0.673
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 2.000     2026   NO    1680          247             261      0.000        75.840        4.234     0.797               3.863   0.792  6.836                 6489.000         -1408.000                0.749
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026  YES    1520          237             491      1.000        64.622        5.823     0.676               2.943  -0.952  6.806                 4474.000         -2654.000                0.671
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000 pre-2026   NO    1091          231             491      0.000        70.361        6.752     0.744               4.066  -0.424  8.594                 4436.000         -1310.000                0.697
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000     2026  YES    1170          231             261      1.000        68.934        5.361     0.740               5.083   0.975  8.956                 5947.000         -2082.000                0.662
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 3.000     2026   NO    1001          215             261      0.000        74.369        5.439     0.787               4.353   0.487  8.040                 4357.000         -1406.000                0.735
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026  YES     862          214             491      1.000        67.619        7.222     0.723               4.654  -0.128  9.155                 4012.000         -1548.000                0.678
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000 pre-2026   NO     834          201             491      0.000        70.953        7.717     0.758               4.826  -0.415  9.534                 4025.000          -984.000                0.692
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000     2026  YES     504          146             261      1.000        65.722        7.298     0.710               5.310  -0.627 10.777                 2676.000         -1003.000                0.664
q_1h (last-hour smile, sensitivity) maker (OPTIMISTIC: assumes fills) 5.000     2026   NO     397          125             261      0.000        71.856        7.828     0.748               2.955  -3.272  9.204                 1173.000         -1464.000                0.760
```
## Monthly P&L (primary q)
```
  period   month  trades  days  pnl_per_contract_c  total_usd                             style   T_c
    2026 2026-01      46    18              -9.870   -454.020                             taker 2.000
    2026 2026-02     127    20               2.136    271.260                             taker 2.000
    2026 2026-03     118    22               5.094    601.150                             taker 2.000
    2026 2026-04      51    15               5.305    270.550                             taker 2.000
    2026 2026-05      65    19              -5.856   -380.660                             taker 2.000
    2026 2026-06     114    21              -7.374   -840.590                             taker 2.000
    2026 2026-07      97    23               1.684    163.360                             taker 2.000
    2026 2026-08     138    20               4.192    578.530                             taker 2.000
    2026 2026-09     134    22               4.425    592.920                             taker 2.000
pre-2026 2024-06       2     1              10.310     20.620                             taker 2.000
pre-2026 2024-08       2     2              18.055     36.110                             taker 2.000
pre-2026 2024-10       1     1               9.360      9.360                             taker 2.000
pre-2026 2024-11      68    14               4.031    274.130                             taker 2.000
pre-2026 2024-12      57    17               1.378     78.520                             taker 2.000
pre-2026 2025-01      64    14              11.395    729.280                             taker 2.000
pre-2026 2025-02      63    17               1.651    104.000                             taker 2.000
pre-2026 2025-03      25     9               5.390    134.760                             taker 2.000
pre-2026 2025-04      17    10              17.109    290.860                             taker 2.000
pre-2026 2025-05      16    10              -5.823    -93.160                             taker 2.000
pre-2026 2025-06      13     9              23.055    299.710                             taker 2.000
pre-2026 2025-07      10     8              11.438    114.380                             taker 2.000
pre-2026 2025-08      23    12               4.442    102.160                             taker 2.000
pre-2026 2025-09      19     8              -7.233   -137.420                             taker 2.000
pre-2026 2025-10      26    10              -7.957   -206.870                             taker 2.000
pre-2026 2025-11      60    10               9.432    565.940                             taker 2.000
pre-2026 2025-12      49    19              -7.312   -358.310                             taker 2.000
    2026 2026-01      31    13             -11.622   -360.270                             taker 3.000
    2026 2026-02      92    17               6.679    614.460                             taker 3.000
    2026 2026-03      57    18               5.616    320.140                             taker 3.000
    2026 2026-04      29    11               7.400    214.600                             taker 3.000
    2026 2026-05      39    12              -7.618   -297.100                             taker 3.000
    2026 2026-06      71    15              -8.734   -620.080                             taker 3.000
    2026 2026-07      60    12               1.319     79.130                             taker 3.000
    2026 2026-08     107    18               6.078    650.320                             taker 3.000
    2026 2026-09      87    19               4.380    381.070                             taker 3.000
pre-2026 2024-06       1     1               9.360      9.360                             taker 3.000
pre-2026 2024-08       1     1               4.660      4.660                             taker 3.000
pre-2026 2024-10       1     1               9.360      9.360                             taker 3.000
pre-2026 2024-11      57    14               7.394    421.440                             taker 3.000
pre-2026 2024-12      37    13               0.018      0.650                             taker 3.000
pre-2026 2025-01      31     9              10.717    332.230                             taker 3.000
pre-2026 2025-02      40    14               7.141    285.640                             taker 3.000
pre-2026 2025-03      14     9              12.354    172.960                             taker 3.000
pre-2026 2025-04      12     7              20.803    249.630                             taker 3.000
pre-2026 2025-05      11     7               0.588      6.470                             taker 3.000
pre-2026 2025-06       8     5              23.986    191.890                             taker 3.000
pre-2026 2025-07       7     5              14.474    101.320                             taker 3.000
pre-2026 2025-08      12     9              10.888    130.650                             taker 3.000
pre-2026 2025-09      13     6             -15.575   -202.480                             taker 3.000
pre-2026 2025-10      15     8             -11.233   -168.490                             taker 3.000
pre-2026 2025-11      51     8              10.641    542.670                             taker 3.000
pre-2026 2025-12      30    13              -6.101   -183.030                             taker 3.000
    2026 2026-01      11     3               0.441      4.850                             taker 5.000
    2026 2026-02      49     9              11.695    573.050                             taker 5.000
    2026 2026-03      13     3              24.421    317.470                             taker 5.000
    2026 2026-04       8     5               1.095      8.760                             taker 5.000
    2026 2026-05      19     6               0.124      2.350                             taker 5.000
    2026 2026-06      26     8             -22.931   -596.200                             taker 5.000
    2026 2026-07      30    10              -8.426   -252.780                             taker 5.000
    2026 2026-08      69    11               5.788    399.370                             taker 5.000
    2026 2026-09      30    10              10.987    329.600                             taker 5.000
pre-2026 2024-11      35    12               5.083    177.900                             taker 5.000
pre-2026 2024-12      13     4               7.934    103.140                             taker 5.000
pre-2026 2025-01       9     2               8.893     80.040                             taker 5.000
pre-2026 2025-02      14     6              17.804    249.260                             taker 5.000
pre-2026 2025-03       5     5              16.848     84.240                             taker 5.000
pre-2026 2025-04      10     6              18.862    188.620                             taker 5.000
pre-2026 2025-05       5     4              15.150     75.750                             taker 5.000
pre-2026 2025-06       3     2              42.803    128.410                             taker 5.000
pre-2026 2025-07       4     2              12.550     50.200                             taker 5.000
pre-2026 2025-08       5     3              17.952     89.760                             taker 5.000
pre-2026 2025-09       7     2               5.661     39.630                             taker 5.000
pre-2026 2025-10       3     2             -20.473    -61.420                             taker 5.000
pre-2026 2025-11      38     5              25.241    959.140                             taker 5.000
pre-2026 2025-12       5     4              17.732     88.660                             taker 5.000
    2026 2026-01     361    31               2.751    993.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-02     487    28               2.187   1065.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-03     517    31               5.696   2945.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-04     445    30               8.231   3663.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-05     340    31               4.812   1636.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-06     397    29              -4.310  -1711.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-07     324    30               2.630    852.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-08     364    27               3.610   1314.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-09     388    28               3.858   1497.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2024-07       1     1               3.000      3.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2024-09       1     1               6.000      6.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2024-11     157    17               9.185   1442.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2024-12     294    30               2.058    605.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-01     452    30               8.737   3949.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-02     318    27               3.009    957.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-03      95     8              13.274   1261.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-04       2     1               3.000      6.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-05       4     3               7.500     30.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-06       9     1               7.111     64.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-07       1     1              15.000     15.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-08     213    24               4.789   1020.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-09     251    25               4.681   1175.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-10     324    26               5.410   1753.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-11     346    27              -1.231   -426.000 maker (OPTIMISTIC: assumes fills) 2.000
pre-2026 2025-12     351    30              -1.766   -620.000 maker (OPTIMISTIC: assumes fills) 2.000
    2026 2026-01     250    31               4.720   1180.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-02     357    28               1.899    678.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-03     344    29               6.433   2213.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-04     279    29               9.416   2627.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-05     198    30               4.732    937.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-06     237    28              -6.110  -1448.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-07     179    28               2.749    492.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-08     244    27               3.168    773.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-09     231    26               4.459   1030.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2024-09       1     1               6.000      6.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2024-11     147    17               9.667   1421.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2024-12     289    30               3.498   1011.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-01     402    30               9.500   3819.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-02     279    27               8.254   2303.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-03      88     8               8.477    746.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-04       2     1               3.000      6.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-05       4     3               7.500     30.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-06       9     1              12.111    109.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-07       1     1              15.000     15.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-08     213    24               3.300    703.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-09     247    25               5.304   1310.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-10     321    26               3.866   1241.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-11     303    27              -0.752   -228.000 maker (OPTIMISTIC: assumes fills) 3.000
pre-2026 2025-12     277    30              -2.079   -576.000 maker (OPTIMISTIC: assumes fills) 3.000
    2026 2026-01     115    29               8.304    955.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-02     188    24               7.702   1448.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-03     141    24               7.418   1046.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-04     102    23              12.363   1261.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-05      75    17               2.107    158.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-06      92    18              -7.196   -662.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-07      69    17              -1.536   -106.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-08     151    21               5.185    783.000 maker (OPTIMISTIC: assumes fills) 5.000
    2026 2026-09      96    19               7.417    712.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2024-09       1     1               6.000      6.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2024-11     117    17               9.658   1130.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2024-12     223    30               6.480   1445.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-01     225    28              13.627   3066.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-02     145    24              11.290   1637.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-03      52     7              10.115    526.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-04       2     1             -33.500    -67.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-05       3     3               2.667      8.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-08     161    23              -0.267    -43.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-09     162    25               4.784    775.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-10     250    25               3.092    773.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-11     160    26              -2.469   -395.000 maker (OPTIMISTIC: assumes fills) 5.000
pre-2026 2025-12     142    28              -6.725   -955.000 maker (OPTIMISTIC: assumes fills) 5.000
```