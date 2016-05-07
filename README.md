AWS Reactive Auto Scaling
=========================

Depends on consul to orchestrate only running this on one instance of a cluster.

Current semi-naive scaling calculation:
- If the CPU percentage is over 90% double the size of the cluster
- Else If the CPU percentage is over 60% add an instance to the cluster
- Else If removing an instance would not put the cpu usage over the limit then remove an instance

Instructions
============
```
  sudo make install
  vi .env.json
  make run
```

TODO
====
- daemonize
- use environment variables instead of the .evn.json file
- make the threshold configurable
- use consul service monitor to determine when the autoscaling group size changed
- collect other system metrics
