"""
    Example of ModECI MDF - Testing integrate and fire neurons
"""

from modeci_mdf.mdf import *
import sys
import numpy
import random

random.seed(1234)


def create_iaf_node(
    id, num_cells=1, v0=-60, erev=-70, thresh=-20, tau=10.0, syn_tau=10
):

    ## IAF node...
    iaf_node = Node(id)

    ip_current = InputPort(id="current_input", shape="(%i,)" % num_cells)
    iaf_node.input_ports.append(ip_current)

    ip_spike = InputPort(id="spike_input", shape="(%i,)" % num_cells)
    iaf_node.input_ports.append(ip_spike)

    syn_tau = Parameter(id="syn_tau", value=syn_tau)
    iaf_node.parameters.append(syn_tau)

    v0 = Parameter(
        id="v0",
        value=numpy.array([v0] * num_cells) if isinstance(v0, (int, float)) else v0,
    )
    iaf_node.parameters.append(v0)

    erev = Parameter(id="erev", value=numpy.array([erev] * num_cells))
    iaf_node.parameters.append(erev)

    tau = Parameter(id="tau", value=tau)
    iaf_node.parameters.append(tau)

    thresh = Parameter(id="thresh", value=numpy.array([thresh] * num_cells))
    iaf_node.parameters.append(thresh)

    spike_weights = Parameter(id="spike_weights", value=numpy.identity(num_cells))
    iaf_node.parameters.append(spike_weights)

    weighted_spike = Parameter(
        id="weighted_spike",
        function="MatMul",
        args={"A": spike_weights.id, "B": ip_spike.id},
    )
    iaf_node.parameters.append(weighted_spike)

    pc = ParameterCondition(
        id="spike_detected",
        test="%s > 0" % ip_spike.id,
        value="%s" % (weighted_spike.id),
    )

    syn_i = Parameter(
        id="syn_i",
        default_initial_value="0",
        time_derivative="-1 * syn_i",
    )
    syn_i.conditions.append(pc)
    iaf_node.parameters.append(syn_i)

    pc1 = ParameterCondition(id="is_spiking", test="v >= thresh", value="1")
    pc2 = ParameterCondition(id="not_spiking", test="v < thresh", value="0")

    spiking = Parameter(
        id="spiking",
        default_initial_value="0",
    )
    spiking.conditions.append(pc1)
    spiking.conditions.append(pc2)
    iaf_node.parameters.append(spiking)

    pc = ParameterCondition(id="reset", test="v > thresh", value="erev")

    v = Parameter(
        id="v",
        default_initial_value="v0",
        time_derivative=f"-1 * (v-erev)/tau + {syn_i.id} + {ip_current.id}",
    )
    v.conditions.append(pc)

    iaf_node.parameters.append(v)

    op_v = OutputPort(id="out_port_v", value="v")
    iaf_node.output_ports.append(op_v)

    op_spiking = OutputPort(id="out_port_spiking", value="spiking")
    iaf_node.output_ports.append(op_spiking)

    return iaf_node


def main():
    mod = Model(id="IAFs")

    net = "-net" in sys.argv
    net2 = "-net2" in sys.argv
    if net:
        mod.id = "IAF_net"
    if net2:
        mod.id = "IAF_net2"

    num_cells = 8 if net or net2 else 1

    mod_graph = Graph(id="iaf_example")
    mod.graphs.append(mod_graph)

    ## Current input node
    input_node = Node(id="current_input_node")

    t_param = Parameter(id="time", default_initial_value=0, time_derivative="1")
    input_node.parameters.append(t_param)

    start = Parameter(id="start", value=20)
    input_node.parameters.append(start)

    dur = Parameter(id="duration", value=60)
    input_node.parameters.append(dur)

    amp = Parameter(id="amplitude", value=10)
    input_node.parameters.append(amp)

    if num_cells > 1:
        amp.value = numpy.array([random.random() * 20 for r in range(num_cells)])

    if net2:
        amp.value = 15
        start.value = numpy.arange(10, 10 * (num_cells + 1), 10)
        dur.value = numpy.ones(num_cells) * 5
        # t_param.default_initial_value = numpy.zeros(num_cells)
        # t_param.time_derivative = str([0]*num_cells)

    level = Parameter(id="level", value=0)

    level.conditions.append(
        ParameterCondition(id="on", test="time > start", value=amp.id)
    )
    level.conditions.append(
        ParameterCondition(
            id="off", test="time > start + duration", value="amplitude*0"
        )
    )

    input_node.parameters.append(level)

    op1 = OutputPort(id="out_port", value=level.id)
    input_node.output_ports.append(op1)

    mod_graph.nodes.append(input_node)

    v0 = (
        numpy.array([random.random() * 20 - 70 for r in range(num_cells)])
        if net
        else -70
        if net2
        else -60
    )

    iaf_node1 = create_iaf_node("pre", num_cells, v0)

    mod_graph.nodes.append(iaf_node1)

    e1 = Edge(
        id="input_edge",
        sender=input_node.id,
        sender_port=input_node.get_output_port("out_port").id,
        receiver=iaf_node1.id,
        receiver_port=iaf_node1.get_input_port("current_input").id,
    )

    mod_graph.edges.append(e1)
    mod_graph.nodes.append(iaf_node1)

    iaf_node2 = create_iaf_node("post", num_cells, v0)
    mod_graph.nodes.append(iaf_node2)

    if net2:
        iaf_node2.get_parameter("tau").value = 1

    weight = [40]
    if net:
        weight = numpy.ones([num_cells, num_cells]) * 40
    if net2:
        weight = numpy.identity(num_cells)
        for i in range(num_cells):
            weight[i, i] = i

    iaf_node2.get_parameter("spike_weights").value = weight

    e2 = Edge(
        id="syn_edge",
        sender=iaf_node1.id,
        sender_port=iaf_node1.get_output_port("out_port_spiking").id,
        receiver=iaf_node2.id,
        receiver_port=iaf_node2.get_input_port("spike_input").id,
    )

    mod_graph.edges.append(e2)

    j_file = "%s.json" % mod.id
    new_file = mod.to_json_file(j_file)
    print("Saved to %s" % j_file)
    y_file = "%s.yaml" % mod.id
    new_file = mod.to_yaml_file(y_file)
    print("Saved to %s" % y_file)

    if "-run" in sys.argv:

        verbose = "-v" in sys.argv

        from modeci_mdf.utils import load_mdf, print_summary

        from modeci_mdf.execution_engine import EvaluableGraph

        eg = EvaluableGraph(mod_graph, verbose)
        dt = 0.1

        duration = 100

        t_ext = 0.0
        recorded = {}
        times = []
        t = []
        i = []
        s1 = []
        sp1 = []
        s2 = []
        sp2 = []

        while t_ext <= duration:
            times.append(t_ext)
            print("======   Evaluating at t = %s  ======" % (t_ext))
            if t_ext == 0:
                eg.evaluate()  # replace with initialize?
            else:
                eg.evaluate(time_increment=dt)

            print(
                "  Out v: %s"
                % eg.enodes["post"].evaluable_outputs["out_port_v"].curr_value
            )

            i.append(eg.enodes[input_node.id].evaluable_outputs["out_port"].curr_value)
            t.append(eg.enodes[input_node.id].evaluable_parameters["time"].curr_value)
            s1.append(eg.enodes["pre"].evaluable_outputs["out_port_v"].curr_value)
            sp1.append(eg.enodes["pre"].evaluable_parameters["spiking"].curr_value)
            s2.append(eg.enodes["post"].evaluable_outputs["out_port_v"].curr_value)
            sp2.append(eg.enodes["post"].evaluable_parameters["spiking"].curr_value)
            t_ext += dt

        import matplotlib.pyplot as plt

        figure, axis = plt.subplots(4, 1, figsize=(7, 7))

        # axis[0].plot(times, t, label="time at input node")

        if type(i[0]) == numpy.ndarray and i[0].size > 1:
            for ii in range(len(i[0])):
                iii = []
                for ti in range(len(t)):
                    iii.append(i[ti][ii])
                axis[0].plot(
                    times, iii, label="Input node %s current" % ii, linewidth="0.5"
                )
        else:
            axis[0].plot(times, i, label="Input node current", color="k")

        if not (net or net2):
            axis[0].legend()

        if type(s1[0]) == numpy.ndarray and s1[0].size > 1:
            for si in range(len(s1[0])):
                ss = []
                for ti in range(len(t)):
                    ss.append(s1[ti][si])
                axis[1].plot(times, ss, label="IaF pre %s v" % si, linewidth="0.5")
        else:
            axis[1].plot(times, s1, label="IaF pre v", color="r")

        if not (net or net2):
            axis[1].legend()

        if type(s2[0]) == numpy.ndarray and s2[0].size > 1:
            for si in range(len(s2[0])):
                ss = []
                for ti in range(len(t)):
                    ss.append(s2[ti][si])
                axis[2].plot(times, ss, label="IaF post %s v" % si, linewidth="0.5")
        else:
            axis[2].plot(times, s2, label="IaF post v", color="b")

        if not (net or net2):
            axis[2].legend()

        if type(sp1[0]) == numpy.ndarray and sp1[0].size > 1:
            for spi1 in range(len(sp1[0])):
                sps1 = []
                for ti in range(len(t)):
                    sps1.append(sp1[ti][spi1])

                nz = [t * dt for t in numpy.nonzero(sps1)][0]
                axis[3].plot(
                    nz, numpy.ones(len(nz)) * spi1, marker=".", color="r", linewidth=0
                )

            for spi in range(len(sp2[0])):
                sps = []
                for ti in range(len(t)):
                    sps.append(sp2[ti][spi])

                nz = [t * dt for t in numpy.nonzero(sps)][0]
                axis[3].plot(
                    nz,
                    numpy.ones(len(nz)) * spi + num_cells,
                    marker=".",
                    color="b",
                    linewidth=0,
                )
        else:
            nz1 = [t * dt for t in numpy.nonzero(sp1)][0]
            axis[3].plot(
                nz1,
                numpy.zeros(len(nz1)),
                marker=".",
                linewidth=0,
                label="pre",
                color="r",
            )
            nz2 = [t * dt for t in numpy.nonzero(sp2)][0]
            axis[3].plot(
                nz2,
                numpy.ones(len(nz2)),
                marker=".",
                linewidth=0,
                label="post",
                color="b",
            )
            plt.ylim([-1, 2])

            axis[3].legend()

        plt.xlim([0, duration])
        plt.xlabel("Time")

        plt.savefig(
            "IaF%s.run.png" % (".net" if (net) else (".net2" if (net2) else "")),
            bbox_inches="tight",
        )

        if "-nogui" not in sys.argv:
            plt.show()

    if "-graph" in sys.argv:
        mod.to_graph_image(
            engine="dot",
            output_format="png",
            view_on_render=False,
            level=2,
            filename_root="iaf%s" % (".net" if (net) else (".net2" if (net2) else "")),
            is_horizontal=True,
            only_warn_on_fail=True,  # Makes sure test of this doesn't fail on Windows on GitHub Actions
        )

    if "-neuroml" in sys.argv:
        from modeci_mdf.interfaces.neuroml.exporter import mdf_to_neuroml

        net, sim = mdf_to_neuroml(
            mod_graph, save_to="%s.nmllite.json" % mod.id, run_duration_sec=100
        )

        from neuromllite.NetworkGenerator import generate_and_run

        generate_and_run(sim, simulator="jNeuroML")

    return mod_graph


if __name__ == "__main__":
    main()
