# Lateral capacity of suction bucket foundations under combined loading

## Abstract

We measure the lateral capacity of tripod suction bucket foundations in dense sand under monotonic and cyclic loading. 42 centrifuge tests at 100g show that embedment ratio L/D governs capacity more strongly than soil relative density. Capacity drops 18% after 1000 cycles at 60% of static capacity. A BNWF model calibrated to centrifuge data predicts capacity within 7% for L/D between 0.5 and 2.0.

## Introduction

Suction bucket foundations support an increasing share of offshore wind turbines. Design codes require lateral capacity checks, but the interaction between soil nonlinearity, embedment geometry, and cyclic degradation is poorly captured by simplified p-y methods.

This paper presents centrifuge test data for tripod suction buckets and develops a beam-on-nonlinear-Winkler-foundation (BNWF) model that matches the observed response. We focus on two questions: (1) which geometric parameter controls lateral capacity, and (2) how much capacity is lost under realistic cyclic loading.

The tests were conducted at the University of Western Australia centrifuge facility. Prior work by Byrne and Houlsby (2003) established monotonic capacity for single buckets; we extend this to tripod configurations and add cyclic data.

## Test programme

We tested 14 model tripods at 100g in dry silica sand (Dr = 65% and 85%). Each tripod had three buckets with D = 4 m and L/D ranging from 0.5 to 2.0 at prototype scale. Load was applied at the hub height through a servo-controlled actuator.

Monotonic tests used displacement control at 0.01 mm/s (prototype). Cyclic tests applied sinusoidal load at 0.1 Hz for 1000 cycles at load ratios of 0.4, 0.6, and 0.8 times the monotonic capacity.

Instrumentation included six strain gauges per bucket wall, pore pressure transducers at the bucket tip, and a laser displacement system tracking hub displacements in three axes.

## Results

The monotonic capacity normalised by Gs*D^3 collapses onto a single curve when plotted against L/D. Dr had a secondary effect: capacity at Dr = 85% exceeded Dr = 65% by only 12%, while doubling L/D from 0.5 to 1.0 increased capacity by 180%.

Cyclic tests at 0.6Qult showed two-phase behaviour. In the first 200 cycles, stiffness increased slightly as the sand densified. Beyond 200 cycles, stiffness degraded monotonically. Net capacity loss at 1000 cycles was 18 +/- 3%.

At 0.4Qult, no measurable degradation occurred (< 2% after 1000 cycles). At 0.8Qult, rapid degradation led to failure at cycle 340 on average.

Pore pressure measurements confirmed drained conditions throughout; the loading frequency was too low for significant excess pore pressure generation.

## Numerical model

The BNWF model uses API RP 2GEO p-y springs with two modifications. First, we replace the initial stiffness with values from small-strain FE analysis (Plaxis 3D, Hardening Soil Small model). Second, we add a cyclic degradation multiplier calibrated to the centrifuge data:

p_cyc(N) = p_static * (1 - delta * ln(N))

where delta = 0.023 for Dr = 65% and delta = 0.019 for Dr = 85%.

The model predicts monotonic capacity within 7% and cyclic degradation within 11% for all 42 tests. Without the small-strain correction, errors increase to 25%.

## Discussion

Two findings deserve attention. First, the dominance of L/D over Dr contradicts the API assumption that capacity scales primarily with soil strength. For suction buckets, the failure mechanism transitions from wedge to flow-around at L/D ~ 1.5, which fundamentally changes the capacity. Any p-y method that ignores this transition will underpredict capacity for deep buckets.

Second, cyclic degradation at moderate load levels (0.6Qult) is gradual and predictable. The logarithmic degradation law holds up well, which is encouraging for lifetime predictions. However, at 0.8Qult, the transition to rapid failure suggests a threshold load ratio exists below which cyclic effects are manageable.

Limitations: we tested only drained conditions in uniform sand. Offshore soils are layered, and partially drained conditions may accelerate degradation. Field validation against the Horns Rev 2 monitoring data is ongoing.
