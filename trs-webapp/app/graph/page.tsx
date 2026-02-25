"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { getGraphData } from "@/lib/api";
import type { GraphData, GraphNode, GraphEdge } from "@/lib/api";

interface D3Node extends GraphNode {
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    fx?: number | null;
    fy?: number | null;
    component?: number;
}

interface D3Edge extends GraphEdge {
    source: number | D3Node;
    target: number | D3Node;
}

const ARROW_BINS = 10;

function clamp01(v: any) {
    const n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(1, n));
}

function nodeColorForReputation(overall: number) {
    return d3.interpolateRdYlGn(clamp01(overall));
}

function edgeColorForWeight(weight: number) {
    const v = clamp01(weight);
    return d3.interpolateBlues(0.25 + 0.75 * v);
}

function weightBin(weight: number) {
    const v = clamp01(weight);
    return Math.min(ARROW_BINS - 1, Math.floor(v * ARROW_BINS));
}

export default function GraphPage() {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<GraphData | null>(null);
    const [threshold, setThreshold] = useState(0.2);
    const [focusUserId, setFocusUserId] = useState<number | null>(null);
    const [status, setStatus] = useState("Loading graph...");

    const containerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        let mounted = true;

        async function loadGraph() {
            try {
                setStatus("Loading graph...");
                const graphData = await getGraphData();
                if (!mounted) return;
                setData(graphData);
                setLoading(false);
                setStatus("Graph loaded");
            } catch (err) {
                const message =
                    err instanceof Error ? err.message : "Failed to load graph";
                setError(message);
                setStatus("Failed to load graph data. Check server logs.");
                setLoading(false);
            }
        }

        loadGraph();

        return () => {
            mounted = false;
        };
    }, []);

    useEffect(() => {
        if (!data || !containerRef.current) return;

        const container = d3.select(containerRef.current);

        // Remove old svg
        container.selectAll("svg").remove();

        const width = containerRef.current.clientWidth || 900;
        const height = Math.max(420, containerRef.current.clientHeight || 600);

        const svg = container
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", `0 0 ${width} ${height}`);

        const defs = svg.append("defs");
        function ensureArrowMarkers() {
            if (!defs.select("#arrow-0").empty()) return;
            for (let i = 0; i < ARROW_BINS; i++) {
                const mid = (i + 0.5) / ARROW_BINS;
                defs
                    .append("marker")
                    .attr("id", `arrow-${i}`)
                    .attr("viewBox", "0 -5 10 10")
                    .attr("refX", 18)
                    .attr("refY", 0)
                    .attr("markerWidth", 6)
                    .attr("markerHeight", 6)
                    .attr("orient", "auto")
                    .append("path")
                    .attr("d", "M0,-5L10,0L0,5")
                    .attr("fill", edgeColorForWeight(mid))
                    .attr("fill-opacity", 0.95);
            }
        }

        ensureArrowMarkers();

        const containerG = svg.append("g");

        const zoom = d3
            .zoom()
            .scaleExtent([0.2, 4])
            .on("zoom", (event) =>
                containerG.attr("transform", (event as any).transform),
            );

        svg.call(zoom as any);

        const thresholdVal = threshold;
        const edges: D3Edge[] = data.edges
            .filter((e) => e.weight >= thresholdVal)
            .map((e) => ({ ...e }));

        const usedNodeIds = new Set<number>();
        for (const e of edges) {
            usedNodeIds.add(e.source as number);
            usedNodeIds.add(e.target as number);
        }

        const nodes: D3Node[] = data.nodes
            .filter((n) => usedNodeIds.has(n.id))
            .map((n) => ({ ...n }));

        if (nodes.length === 0) {
            setStatus("No edges at this threshold. Lower the threshold to see more.");
            return;
        }

        const nodeRadius = d3.scaleSqrt().domain([0, 1]).range([8, 28]);
        const edgeWidth = d3.scaleLinear().domain([0, 1]).range([1, 7]);
        const edgeOpacity = d3.scaleLinear().domain([0, 1]).range([0.15, 0.95]);

        const simNodes: D3Node[] = nodes;
        const simEdges: D3Edge[] = edges;

        function assignComponents(simNodesLocal: D3Node[], simEdgesLocal: D3Edge[]) {
            const neighbors = new Map<number, number[]>();
            for (const n of simNodesLocal) neighbors.set(n.id, []);
            for (const e of simEdgesLocal) {
                const s = e.source as number;
                const t = e.target as number;
                if (!neighbors.has(s) || !neighbors.has(t)) continue;
                neighbors.get(s)!.push(t);
                neighbors.get(t)!.push(s);
            }
            const compById = new Map<number, number>();
            let comp = 0;
            for (const n of simNodesLocal) {
                if (compById.has(n.id)) continue;
                const stack = [n.id];
                compById.set(n.id, comp);
                while (stack.length) {
                    const v = stack.pop()!;
                    const adj = neighbors.get(v) || [];
                    for (const u of adj) {
                        if (!compById.has(u)) {
                            compById.set(u, comp);
                            stack.push(u);
                        }
                    }
                }
                comp += 1;
            }
            for (const n of simNodesLocal) n.component = compById.get(n.id) ?? 0;
            return comp;
        }

        const componentCount = assignComponents(simNodes, simEdges);
        const anchorR = Math.max(0, Math.min(width, height) / 2);
        const anchors = new Array(Math.max(1, componentCount)).fill(null).map((_, k) => {
            if (componentCount <= 1) return { x: width / 2, y: height / 2 };
            const a = (2 * Math.PI * k) / componentCount;
            return {
                x: width / 2 + anchorR * Math.cos(a),
                y: height / 2 + anchorR * Math.sin(a),
            };
        });

        const simulation = d3
            .forceSimulation<D3Node>(simNodes)
            .force(
                "link",
                d3
                    .forceLink<D3Node, D3Edge>(simEdges)
                    .id((d: any) => d.id)
                    .distance(220)
                    .strength(0.45),
            )
            .force(
                "charge",
                d3.forceManyBody().strength(-260).distanceMax(220),
            )
            .force(
                "componentX",
                d3
                    .forceX<D3Node>(
                        (d: any) => anchors[d.component ?? 0]?.x ?? width / 2,
                    )
                    .strength(0.13),
            )
            .force(
                "componentY",
                d3
                    .forceY<D3Node>(
                        (d: any) => anchors[d.component ?? 0]?.y ?? height / 2,
                    )
                    .strength(0.13),
            )
            .force(
                "collide",
                d3
                    .forceCollide<D3Node>()
                    .radius(
                        (d: any) => nodeRadius(clamp01(d.reputation_overall)) + 18,
                    )
                    .iterations(2),
            );

        const link = containerG
            .append("g")
            .attr("stroke-linecap", "round")
            .selectAll<SVGLineElement, D3Edge>("line")
            .data(simEdges)
            .join("line")
            .attr("stroke-width", (d: any) => edgeWidth(d.weight))
            .attr("stroke-opacity", (d: any) => edgeOpacity(d.weight))
            .attr("stroke", (d: any) => edgeColorForWeight(d.weight))
            .attr("marker-end", (d: any) => `url(#arrow-${weightBin(d.weight)})`);

        link
            .append("title")
            .text((d: any) => {
                const s = (d.source as D3Node).id ?? d.source;
                const t = (d.target as D3Node).id ?? d.target;
                return `edge ${s} → ${t}\nweight=${(d.weight || 0).toFixed(
                    3,
                )}\nratings=${d.count || 0}`;
            });

        const node = containerG
            .append("g")
            .selectAll<SVGGElement, D3Node>("g")
            .data(simNodes)
            .join("g")
            .style("cursor", "pointer")
            .call(
                d3
                    .drag<SVGGElement, D3Node>()
                    .on("start", (event, d) => {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x ?? null;
                        d.fy = d.y ?? null;
                    })
                    .on("drag", (event, d) => {
                        d.fx = event.x;
                        d.fy = event.y;
                    })
                    .on("end", (event, d) => {
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null;
                        d.fy = null;
                    }),
            );

        node
            .append("circle")
            .attr("r", (d: any) => nodeRadius(clamp01(d.reputation_overall)))
            .attr("fill", (d: any) => nodeColorForReputation(d.reputation_overall))
            .attr("fill-opacity", 0.92)
            .attr("stroke", "rgba(33,37,41,0.35)")
            .attr("stroke-width", 1);

        node
            .append("title")
            .text((d: any) => {
                const overall = d.reputation_overall || 0;
                return `${d.id}: ${d.name}\ntrust=${(
                    d.trust || 0
                ).toFixed(4)}\noverall_rep=${overall.toFixed(3)}`;
            });

        node
            .append("text")
            .text((d: any) => d.name)
            .attr("font-size", 12)
            .attr("font-weight", 700)
            .attr(
                "dx",
                (d: any) => nodeRadius(clamp01(d.reputation_overall)) + 6,
            )
            .attr("dy", 4)
            .attr("stroke", "rgba(255,255,255,0.95)")
            .attr("stroke-width", 4)
            .attr("stroke-linejoin", "round")
            .attr("paint-order", "stroke")
            .attr("fill", "rgba(33,37,41,0.0)");

        node
            .append("text")
            .text((d: any) => d.name)
            .attr("font-size", 12)
            .attr("font-weight", 700)
            .attr(
                "dx",
                (d: any) => nodeRadius(clamp01(d.reputation_overall)) + 6,
            )
            .attr("dy", 4)
            .attr("fill", "rgba(33,37,41,0.90)");

        function computeNeighborhood(edgeList: D3Edge[], focusId: number | null) {
            const neigh = new Set<number>();
            if (focusId == null) return neigh;
            neigh.add(focusId);
            for (const e of edgeList) {
                const s = (e.source as D3Node).id ?? e.source;
                const t = (e.target as D3Node).id ?? e.target;
                if (s === focusId) neigh.add(t as number);
                if (t === focusId) neigh.add(s as number);
            }
            return neigh;
        }

        function applyHighlight(focusId: number | null) {
            if (focusId == null) {
                node
                    .selectAll("circle")
                    .attr(
                        "fill",
                        (d: any) => nodeColorForReputation(d.reputation_overall),
                    )
                    .attr("fill-opacity", 0.92);
                link
                    .attr("stroke-opacity", (d: any) => edgeOpacity(d.weight))
                    .attr("stroke", (d: any) => edgeColorForWeight(d.weight));
                return;
            }
            const neigh = computeNeighborhood(simEdges, focusId);
            node
                .selectAll<SVGCircleElement, D3Node>("circle")
                .attr("fill", (d: any) =>
                    d.id === focusId
                        ? "var(--bs-warning)"
                        : neigh.has(d.id)
                            ? nodeColorForReputation(d.reputation_overall)
                            : "var(--bs-secondary)",
                )
                .attr("fill-opacity", (d: any) =>
                    neigh.has(d.id) ? 0.95 : 0.12,
                );
            link.attr("stroke-opacity", (d: any) => {
                const s = (d.source as D3Node).id ?? d.source;
                const t = (d.target as D3Node).id ?? d.target;
                return s === focusId || t === focusId
                    ? edgeOpacity(d.weight)
                    : 0.05;
            });
        }

        node.on("click", (_event, d) => {
            setFocusUserId(d.id);
            applyHighlight(d.id);
            const k = 1.3;
            const tx = width / 2 - (d.x ?? 0) * k;
            const ty = height / 2 - (d.y ?? 0) * k;
            svg
                .transition()
                .duration(450)
                .call(
                    (zoom as any).transform,
                    d3.zoomIdentity.translate(tx, ty).scale(k),
                );
        });

        simulation.on("tick", () => {
            link
                .attr("x1", (d: any) => (d.source as D3Node).x ?? 0)
                .attr("y1", (d: any) => (d.source as D3Node).y ?? 0)
                .attr("x2", (d: any) => (d.target as D3Node).x ?? 0)
                .attr("y2", (d: any) => (d.target as D3Node).y ?? 0);
            node.attr(
                "transform",
                (d: any) => `translate(${d.x ?? 0},${d.y ?? 0})`,
            );
        });

        applyHighlight(focusUserId);

        const focusPresent =
            focusUserId == null || usedNodeIds.has(focusUserId);
        if (focusUserId != null && !focusPresent) {
            setStatus(
                `Focused user is filtered out by threshold ${thresholdVal.toFixed(
                    2,
                )}. Lower the threshold to see them.`,
            );
        } else {
            setStatus(
                `${nodes.length} users, ${edges.length} edges shown (threshold ${thresholdVal.toFixed(
                    2,
                )}).`,
            );
        }

        // cleanup on unmount
        return () => {
            simulation.stop();
            container.selectAll("svg").remove();
        };
    }, [data, threshold, focusUserId]);

    if (error) {
        return (
            <div className="p-4 bg-red-50 border border-red-300 rounded">
                <h1 className="text-xl font-semibold mb-2">Error loading graph</h1>
                <p className="text-red-700">{error}</p>
            </div>
        );
    }

    if (loading || !data) {
        return (
            <div className="p-4 border rounded bg-white">
                <h1 className="text-xl font-semibold mb-2">Rating graph</h1>
                <p className="text-sm text-gray-600">{status}</p>
            </div>
        );
    }

    return (
        <>
            <div className="flex items-center justify-between mb-3">
                <div>
                    <h1 className="text-2xl font-semibold mb-1">Rating graph</h1>
                    <div className="text-sm text-muted-foreground">
                        Directed edges are{" "}
                        <span className="font-semibold">rater → ratee</span>. Edge
                        thickness/color = local weight (0–1). Node color/size = overall
                        reputation.
                    </div>
                </div>
            </div>

            <div className="bg-white border rounded-lg p-4 shadow-sm">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Focus user
                        </label>
                        <input
                            type="text"
                            placeholder="Type a name or ID"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            onChange={(e) => {
                                const input = e.target.value.toLowerCase();
                                if (data && input) {
                                    const node = data.nodes.find(
                                        (n) =>
                                            n.name.toLowerCase().includes(input) ||
                                            String(n.id) === input,
                                    );
                                    if (node) setFocusUserId(node.id);
                                }
                            }}
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            Click a node in the graph too
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Edge weight threshold:{" "}
                            <span className="font-semibold">
                                {threshold.toFixed(2)}
                            </span>
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={threshold}
                            onChange={(e) => setThreshold(parseFloat(e.target.value))}
                            className="w-full"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            Higher = fewer, stronger edges
                        </p>
                    </div>

                    <div>
                        <button
                            onClick={() => setFocusUserId(null)}
                            className="w-full px-4 py-2 bg-gray-100 border border-gray-300 rounded-md text-sm font-medium hover:bg-gray-50"
                        >
                            Reset view
                        </button>
                    </div>
                </div>

                <div className="text-sm text-muted-foreground mb-2">
                    {status}
                </div>

                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground mb-4">
                    <span>Node reputation:</span>
                    <span>low</span>
                    <div className="w-44 h-2.5 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded border border-gray-300" />
                    <span>high</span>
                    <div className="ms-auto">
                        Edge thickness/color = vote strength
                    </div>
                </div>

                <div
                    id="graph-container"
                    ref={containerRef}
                    className="w-full rounded border border-gray-200 bg-white"
                    style={{
                        height: "500px",
                        minHeight: "420px",
                        position: "relative",
                    }}
                />

                <div className="mt-4 pt-4 border-t">
                    <div className="mb-4">
                        <div className="font-semibold text-sm mb-2">
                            Graph Summary
                        </div>
                        {data && (
                            <div className="text-sm text-muted-foreground">
                                <p>Total users: {data.nodes.length}</p>
                                <p>Total rating relationships: {data.edges.length}</p>
                                <p>
                                    Visible relationships (threshold {threshold.toFixed(2)}
                                    ):{" "}
                                    {
                                        data.edges.filter(
                                            (e) => e.weight >= threshold,
                                        ).length
                                    }
                                </p>
                            </div>
                        )}
                    </div>

                    {focusUserId && data && (
                        <div className="mt-4">
                            <div className="font-semibold text-sm mb-2">
                                Focused User Details
                            </div>
                            {data.nodes.find((n) => n.id === focusUserId) && (
                                <div className="text-sm text-muted-foreground">
                                    {(() => {
                                        const node = data.nodes.find(
                                            (n) => n.id === focusUserId,
                                        );
                                        if (!node) return null;
                                        const incomingEdges = data.edges.filter(
                                            (e) => e.target === focusUserId,
                                        );
                                        const outgoingEdges = data.edges.filter(
                                            (e) => e.source === focusUserId,
                                        );
                                        return (
                                            <>
                                                <p>
                                                    <span className="font-medium">Name:</span>{" "}
                                                    {node.name} (ID: {node.id})
                                                </p>
                                                <p>
                                                    <span className="font-medium">
                                                        Overall Reputation:
                                                    </span>{" "}
                                                    {node.reputation_overall.toFixed(2)}/10
                                                </p>
                                                <p>
                                                    <span className="font-medium">
                                                        Trust Score:
                                                    </span>{" "}
                                                    {node.trust.toFixed(2)}
                                                </p>
                                                <p>
                                                    <span className="font-medium">
                                                        Ratings Received:
                                                    </span>{" "}
                                                    {incomingEdges.length}
                                                </p>
                                                <p>
                                                    <span className="font-medium">
                                                        Ratings Given:
                                                    </span>{" "}
                                                    {outgoingEdges.length}
                                                </p>
                                            </>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
