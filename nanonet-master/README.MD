# NANONET-EXT &ndash; an extended version of Nanonet
[Nanonet](https://github.com/segment-routing/nanonet) is a network testing framework, originally written by *David Lebrun* for his PhD thesis and published at [https://github.com/segment-routing/nanonet](https://github.com/segment-routing/nanonet). It is based off [Mininet](http://mininet.org/) and simulates network hosts and routers by creating virtual namespaces on a Linux host and routes between them.

We &ndash; the [Research Group *Communication Technologies*](https://ct.cs.univie.ac.at/) at the University of Vienna &ndash; forked the project and added some additional functionality, such as

* support for custom commands
* throughput measuring for links
* (optional) support for directed link weights for route calculation
* allow to stop the framework automatically (`--stop` parameter)
* allow to fail interfaces from the command line and triggers that are executed after links have failed
* ...

Also, we have ported Nanonet from Python 2 to Python 3.

**Main contact:** Nikolaus Suess &lt;[nikolaus.suess@univie.ac.at](mailto:nikolaus.suess@univie.ac.at)&gt; or <[nikolaus@suess.dev](mailto:nikolaus@suess.dev)><br>
If you have any questions, feel free to get in touch.

## Requirements
* Python 3<br>
Currently, we have tested the framework only with `python3.6`.

* Linux (Kernel >=4.14) for running the scripts

On newer versions of e.g. Debian you might have to install the following packages and modify the `PATH` variable as follows:

```bash
apt install net-tools
apt install iproute2 # should already be installed
PATH=$PATH:/sbin
```

## General procedure
0. Define the network topology in a `*.topo.py` file. (In some cases, these files can also be generated e.g. from JSON files.) Below, you can find an example of a topology file.
0. Compile the topology from a Python script into a Shell script by using <br>
`python3.6 build.py <TOPOLOGY-NAME>.topo.py <TOPOLOGY-NAME>`<br>
This will generate the shell script called `<TOPOLOGY-NAME>.topo.sh`.
0. Run your tests by executing the script (e.g. `bash <TOPOLOGY-NAME>.topo.sh`).
0. After your tests are finished, you might want to stop the framework. This can be done by calling the script with the `--stop` parameter: <br>
`bash <TOPOLOGY-NAME>.topo.sh --stop`

## Topology files
A network topology basically consists of a set of nodes and links between them. To define them, write a class that inherits from `Topo`:

```python
#!/usr/bin/env python3

from node import *

# Topology class
class MyTopology(Topo):
    # Overwriting the build method.
    # It is called before the IP addresses are assigned. Here, the nodes and links must be defined.
    # This overwrite is required.
    def build(self):
        # If you want to disable the default route calculation (Dijkstra), you can set self.noroute to True
        # self.noroute = False

        # Add 3 nodes, called X, Y and Z
        self.add_node("X")
        self.add_node("Y")
        self.add_node("Z")

        # Add (bidirectional) links between them.
        self.add_link_name("X", "Y", cost=1, delay=0.2, bw=5000)
        self.add_link_name("X", "Z", cost=1, delay=0.2, bw=5000)
        self.add_link_name("Y", "Z", cost=1, delay=0.2, bw=5000)

    # You can also overwrite the dijkstra_computed method.
    # It is called after the IP addresses have been assigned.
    # This overwrite is optional.
    def dijkstra_computed(self):
        self.add_command("X", "ip -6 route add {Z/} encap seg6 mode encap segs {Y} metric 2048 src {X} via {edge (X,Y) at Y}")
        
        # Optional: Enable per-interface throughput measuring (at all nodes)
        # self.enable_throughput()

# A list of all topologies that can be created with this file.
topos = { 'MyTopology': (lambda: MyTopology()) }
```

**Please note:** If you add routes, e.g., with `add_commands`, do not forget to specify the source node in the route command with `src {NODE}`, too!

## Additional information
### Get IP addresses and interface names
The IP addresses of nodes and interfaces are assigned in a random order. If you generate the script for the same topology more than one time, it is very likely that the IP addresses have changed.

To find out the IP addresses or interface names while testing, you can call the script with special parameters:

```bash
# Find the name of the interface that is at the link from node X to node Y at X
./<TOPOLOGY-NAME>.topo.sh --query "ifname (<X>,<Y>) at <X>"
# Find the name of the interface that is at the link from node X to node Y at Y
./<TOPOLOGY-NAME>.topo.sh --query "ifname (<Y>,<X>) at <Y>"
# Find out the node's IP address
./<TOPOLOGY-NAME>.topo.sh --query "<X>"
# Get the IP address of the interface of the link from X to Y at X
./<TOPOLOGY-NAME>.topo.sh --query "edge (<X>,<Y>) at <X>"
# Get the IP address of the interface of the link from Y to X at Y
./<TOPOLOGY-NAME>.topo.sh --query "edge (<Y>,<X>) at <Y>"
```

To use the IP address or interface name in a predefined (additional) command, you can simply use these expressions:
```
# {Y} will be replaced by the node IP address of Y
# {edge (X,Y) at Y} will be replaced by the IP address of the interface at Y, e.g., "fc00:2:0:1:5::1"
self.add_command("X", "ip -6 route add {Y} via {edge (X,Y) at Y} ...")
self.add_command("X", "ip -6 route add {Z} dev {ifname (X,Z) at X} ...")
# {Y/} is replaced by the IP address, followed by the CIDR, e.g., "fc00:2:0:1:5::1/64"
self.add_command("X", "ip -6 route add {Y/} via {edge (X,Y) at Y} ...")
self.add_command("X", "ip -6 route add {Z/} dev {ifname (X,Z) at X} ...")
```

Of course, you can use as many expressions as you want in the same command.

The expressions are replaced immediately before printing the commands into the shell script file. Hence, you can call the `add_command` method also from the `build(self)` method. However, sometimes it is necessary to process the data within python, too (e.g. for iterating over all possible nexthop IPs). This is not possible inside the `build` method of the class, as by this time the IP addresses are not yet set, but you can do this by overwriting the method `dijkstra_computed(self)`, which gets called after (1) calling the `build` method and (2) setting all IP addresses.

`add_command` also has an optional parameter, `eval = {True, False}` (default `False`). If it is set to `False`, in the bash script files there are single quotes `''` used, which do not allow, e.g., to use global (bash) variables etc. If you like to use them, too, you have to set `eval = True`, which uses `""` instead.

### Fail a link (by failing the interfaces on both sides)
You can fail a link by setting down the interfaces on both sides. This can be done at the command line with:

```
# set link between node X and Y down
./<TOPOLOGY-NAME>.topo.sh --link "edge (<X>,<Y>) down"
# set link between node X and Y up
./<TOPOLOGY-NAME>.topo.sh --link "edge (<X>,<Y>) up"
```

Optionally, you can add triggers that are executed when these commands are executed. You can add such a trigger in your topology file with:

```
def build(self):
        # Add nodes
        self.add_node("X")
        self.add_node("Y")

        # Add (bidirectional) links between them.
        # To add triggers, you need to store the edge in a variable
        link = self.add_link_name("X", "Y", cost=1, delay=0.2, bw=5000)

        # Add the trigger
        # Parameters are node name, command and {up,down}
        # up   is executed with --link ... up
        # down is executed with --link ... down
        link.add_restart_command('X', 'ip -6 route add ...', 'up')
        link.add_restart_command('Y', 'logger ...', 'down')
```

This can be useful to adapt static routes automatically after a link fail.

### Measure the throughput of links
You can measure the traffic per link (more precisely: per interface). To enable this feature, use

```
self.enable_throughput()
```

This will generate one JSON file per node (`<NODE-NAME>.throughput.json`) of the form:

```
{
    "4-0": {
        "recv_bytes": 992, # Number of received bytes of interface 4-0
        "recv_packets": 8, # Number of received packets
        "recv_errs": 0, 
        "recv_drop": 0, 
        "recv_fifo": 0, 
        "recv_frame": 0, 
        "recv_compressed": 0, 
        "recv_multicast": 0, 
        "trans_bytes": 992,  # Number of sent bytes
        "trans_packets": 8,  # Number of sent packets
        "trans_errs": 0, 
        "trans_drop": 0, 
        "trans_fifo": 0, 
        "trans_colls": 0, 
        "trans_carrier": 0, 
        "trans_compressed": 0
    }, 
    "4-1": { ... }
}
```

### Creating network traffic
We recommend to use [`nuttcp`](https://www.nuttcp.net) for creating network traffic. You can install it on Debian-based systems with

```
apt install nuttcp
```

On all network components that you want to communicate with, start a `nuttcp` server with `nuttcp -6 -S`. If you want to add this to you topology script, use `add_command`:

```
        self.add_command("S1", "nuttcp -6 -S")
```

On the clients, you can start flows with (if you want to automate it, you might consider combining it with the `at` command):

```
nuttcp -T<TIME> -i<INTERVALS> [OTHER OPTIONS] <IP ADDRESS>
```

For example, to start a flow from client `X` to server `S1`, run it for 300 seconds and set the interval to 1 second, use:

```
ip netns exec X bash -c "nuttcp -T300 -i1 `./<TOPOLOGY-NAME>.topo.sh --query S1`" >flow_X-S1.txt
```

With our [`nut2csv`](https://github.com/nikolaussuess/nut2csv) tool, you can also convert the output of `nuttcp` to the CSV format. This makes it easier to process the data, e.g., with Python or other programming languages.

### Start a shell on a virtual node
To start a shell on the virtual node, simply call:

```
ip netns exec <NODE-NAME> bash
```

To leave the shell again, use EOF (Strg+D) or `exit`.

Optionally, you can edit your `.bashrc` file to show the name of the current network namespace in the command prompt:

```
# add to .bashrc / edit that file
NETNS=`ip netns identify`
if test "$NETNS" == ""; then
    NETNS='#'
fi

# Change it to whatever you want, but include $NETNS here
PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u\[\033[00m\]:\[\033[01;34m\]($NETNS)\[\033[00m\]\$ '
```
