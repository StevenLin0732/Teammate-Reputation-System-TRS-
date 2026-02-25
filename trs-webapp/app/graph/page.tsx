'use client';

import { useEffect, useState } from 'react';
import { getGraphData } from '@/lib/api';
import type { GraphData, GraphNode, GraphEdge } from '@/lib/api';

interface D3Node extends GraphNode {
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    fx?: number | null;
    fy?: number | null;
}

interface D3Edge extends GraphEdge { }

export default function GraphPage() {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<GraphData | null>(null);
    const [threshold, setThreshold] = useState(0.2);
    const [focusUserId, setFocusUserId] = useState<number | null>(null);
    const [status, setStatus] = useState('Loading graph...');

    useEffect(() => {
        async function loadGraph() {
            try {
                setStatus('Loading graph...');
                const graphData = await getGraphData();
                setData(graphData);
                setLoading(false);
                setStatus('Graph loaded');
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Failed to load graph';
                setError(message);
                setStatus('Failed to load graph data. Check server logs.');
                setLoading(false);
            }
        }
        loadGraph();
    }, []);

    useEffect(() => {
        if (!data || loading) return;

        const container = document.getElementById('graph-container');
        if (!container) return;

        // Clear previous SVG
        const existingSvg = container.querySelector('svg');
        if (existingSvg) {
            existingSvg.remove();
        }

        // Create canvas-like container
        const width = container.clientWidth || 800;
        const height = 600;

        // Create SVG using vanilla DOM (avoiding d3 import complexities)
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', String(width));
        svg.setAttribute('height', String(height));
        svg.setAttribute('style', 'background: white; border: 1px solid #ccc; border-radius: 4px;');
        container.appendChild(svg);

        // Filter edges based on threshold
        const filteredEdges = data.edges.filter(e => e.weight >= threshold);
        const nodeIds = new Set<number>();

        // Get all nodes that have edges
        data.nodes.forEach(n => nodeIds.add(n.id));
        filteredEdges.forEach(e => {
            nodeIds.add(e.source);
            nodeIds.add(e.target);
        });

        const visibleNodes = data.nodes.filter(n => nodeIds.has(n.id));

        // Simple force-directed layout without d3
        const nodes: D3Node[] = visibleNodes.map(n => ({
            ...n,
            x: Math.random() * width,
            y: Math.random() * height,
            vx: 0,
            vy: 0,
            fx: null,
            fy: null,
        }));

        const nodeMap = new Map(nodes.map(n => [n.id, n]));

        // Simple physics simulation
        const simulate = () => {
            // Apply forces
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const dx = nodes[j].x! - nodes[i].x!;
                    const dy = nodes[j].y! - nodes[i].y!;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const repulsion = 200 / dist;

                    nodes[i].vx! -= (dx / dist) * repulsion;
                    nodes[i].vy! -= (dy / dist) * repulsion;
                    nodes[j].vx! += (dx / dist) * repulsion;
                    nodes[j].vy! += (dy / dist) * repulsion;
                }
            }

            // Apply edge attractions
            for (const edge of filteredEdges) {
                const source = nodeMap.get(edge.source);
                const target = nodeMap.get(edge.target);

                if (source && target) {
                    const dx = target.x! - source.x!;
                    const dy = target.y! - source.y!;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const attraction = (dist - 100) * 0.05;

                    source.vx! += (dx / dist) * attraction;
                    source.vy! += (dy / dist) * attraction;
                    target.vx! -= (dx / dist) * attraction;
                    target.vy! -= (dy / dist) * attraction;
                }
            }

            // Update positions with damping
            for (const node of nodes) {
                node.vx! *= 0.85;
                node.vy! *= 0.85;

                if (node.fx !== null) {
                    node.x = node.fx;
                } else {
                    node.x! += node.vx!;
                }

                if (node.fy !== null) {
                    node.y = node.fy;
                } else {
                    node.y! += node.vy!;
                }

                // Keep in bounds
                node.x = Math.max(20, Math.min(width - 20, node.x!));
                node.y = Math.max(20, Math.min(height - 20, node.y!));
            }
        };

        // Initial layout iterations
        for (let i = 0; i < 300; i++) {
            simulate();
        }

        // Draw edges
        for (const edge of filteredEdges) {
            const source = nodeMap.get(edge.source);
            const target = nodeMap.get(edge.target);

            if (!source || !target) continue;

            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', String(source.x));
            line.setAttribute('y1', String(source.y));
            line.setAttribute('x2', String(target.x));
            line.setAttribute('y2', String(target.y));

            // Color based on weight
            const opacity = Math.min(edge.weight, 1);
            const hue = 120 - edge.weight * 120; // green to red
            line.setAttribute('stroke', `hsl(${hue}, 100%, 50%)`);
            line.setAttribute('stroke-width', String(Math.max(0.5, edge.weight * 3)));
            line.setAttribute('opacity', String(opacity));

            svg.appendChild(line);
        }

        // Draw nodes
        for (const node of nodes) {
            const rep = node.reputation_overall || 0;
            const size = Math.max(4, Math.min(12, 4 + rep * 3));

            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', String(node.x));
            circle.setAttribute('cy', String(node.y));
            circle.setAttribute('r', String(size));

            // Color based on reputation
            const hue = 120 * rep / 10;
            circle.setAttribute('fill', `hsl(${hue}, 70%, 50%)`);
            circle.setAttribute('stroke', '#333');
            circle.setAttribute('stroke-width', '1.5');
            circle.setAttribute('style', 'cursor: pointer;');

            // Add hover title
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = `${node.name} (ID: ${node.id}, Rep: ${rep.toFixed(2)}, Trust: ${node.trust.toFixed(2)})`;
            circle.appendChild(title);

            circle.addEventListener('click', () => setFocusUserId(node.id));
            svg.appendChild(circle);
        }

        // Draw labels for focused node
        if (focusUserId) {
            const focusNode = nodeMap.get(focusUserId);
            if (focusNode) {
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', String(focusNode.x! + 15));
                text.setAttribute('y', String(focusNode.y));
                text.setAttribute('fill', '#333');
                text.setAttribute('font-size', '12px');
                text.setAttribute('font-weight', 'bold');
                text.textContent = focusNode.name;
                svg.appendChild(text);
            }
        }
    }, [data, loading, threshold, focusUserId]);

    if (error) {
        return (
            <div className="p-4 bg-red-50 border border-red-300 rounded">
                <h1 className="text-xl font-semibold mb-2">Error loading graph</h1>
                <p className="text-red-700">{error}</p>
            </div>
        );
    }

    return (
        <>
            <div className="flex items-center justify-between mb-3">
                <div>
                    <h1 className="text-2xl font-semibold mb-1">Rating graph</h1>
                    <div className="text-sm text-muted-foreground">
                        Directed edges are <span className="font-semibold">rater → ratee</span>. Edge thickness/color = local weight (0–1). Node color/size = overall reputation.
                    </div>
                </div>
            </div>

            <div className="bg-white border rounded-lg p-4 shadow-sm">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
                    <div>
                        <label className="block text-sm font-medium mb-2">Focus user</label>
                        <input
                            type="text"
                            placeholder="Type a name or ID"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            onChange={(e) => {
                                const input = e.target.value.toLowerCase();
                                if (data && input) {
                                    const node = data.nodes.find(
                                        n => n.name.toLowerCase().includes(input) || String(n.id) === input
                                    );
                                    if (node) setFocusUserId(node.id);
                                }
                            }}
                        />
                        <p className="text-xs text-muted-foreground mt-1">Click a node in the graph too</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2">
                            Edge weight threshold: <span className="font-semibold">{threshold.toFixed(2)}</span>
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
                        <p className="text-xs text-muted-foreground mt-1">Higher = fewer, stronger edges</p>
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

                <div className="text-sm text-muted-foreground mb-2">{status}</div>

                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground mb-4">
                    <span>Node reputation:</span>
                    <span>low</span>
                    <div className="w-44 h-2.5 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded border border-gray-300"></div>
                    <span>high</span>
                    <div className="ms-auto">Edge thickness/color = vote strength</div>
                </div>

                <div
                    id="graph-container"
                    className="w-full rounded border border-gray-200 bg-white"
                    style={{ height: '500px', minHeight: '420px', position: 'relative' }}
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
                                <p>Visible relationships (threshold {threshold.toFixed(2)}): {data.edges.filter(e => e.weight >= threshold).length}</p>
                            </div>
                        )}
                    </div>

                    {focusUserId && data && (
                        <div className="mt-4">
                            <div className="font-semibold text-sm mb-2">
                                Focused User Details
                            </div>
                            {data.nodes.find(n => n.id === focusUserId) && (
                                <div className="text-sm text-muted-foreground">
                                    {(() => {
                                        const node = data.nodes.find(n => n.id === focusUserId);
                                        if (!node) return null;
                                        const incomingEdges = data.edges.filter(e => e.target === focusUserId);
                                        const outgoingEdges = data.edges.filter(e => e.source === focusUserId);
                                        return (
                                            <>
                                                <p><span className="font-medium">Name:</span> {node.name} (ID: {node.id})</p>
                                                <p><span className="font-medium">Overall Reputation:</span> {node.reputation_overall.toFixed(2)}/10</p>
                                                <p><span className="font-medium">Trust Score:</span> {node.trust.toFixed(2)}</p>
                                                <p><span className="font-medium">Ratings Received:</span> {incomingEdges.length}</p>
                                                <p><span className="font-medium">Ratings Given:</span> {outgoingEdges.length}</p>
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
