import React, { useState, useEffect } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { Maximize, Minimize } from 'lucide-react';

cytoscape.use(dagre);

const GraphPanel = ({ modelData, currentStateId, onStateSelect }) => {
    const [elements, setElements] = useState([]);

    useEffect(() => {
        if (!modelData || !modelData.states) return;

        const newElements = [];

        // Add nodes
        modelData.states.forEach(state => {
            newElements.push({
                data: {
                    id: state.id,
                    label: state.name,
                    isTerminal: state.is_terminal,
                    isInitial: state.is_initial,
                    isFault: state.is_fault
                },
                classes: [
                    state.id === currentStateId ? 'active' : '',
                    state.is_terminal ? 'terminal' : '',
                    state.is_initial ? 'initial' : '',
                    state.is_fault ? 'fault' : ''
                ].filter(Boolean).join(' ')
            });
        });

        // Add edges
        modelData.transitions.forEach(t => {
            let label = t.display_label || t.event;
            if (t.guard) {
                // Simple stringification of guard for display
                label += ' [...]';
            }

            newElements.push({
                data: {
                    id: t.id,
                    source: t.from_state,
                    target: t.to_state,
                    label: label
                }
            });
        });

        setElements(newElements);
    }, [modelData, currentStateId]);

    const style = [
        {
            selector: 'node',
            style: {
                'background-color': '#e2e8f0',
                'label': 'data(label)',
                'text-valign': 'center',
                'text-halign': 'center',
                'color': '#1e293b',
                'font-size': '12px',
                'font-weight': 'bold',
                'width': 'label',
                'height': 'label',
                'padding': '16px',
                'shape': 'round-rectangle',
                'border-width': 2,
                'border-color': '#94a3b8'
            }
        },
        {
            selector: 'node.active',
            style: {
                'background-color': '#bfdbfe',
                'border-color': '#3b82f6',
                'border-width': 3,
                'color': '#1e3a8a'
            }
        },
        {
            selector: 'node.terminal',
            style: {
                'border-color': '#ef4444',
                'border-width': 3
            }
        },
        {
            selector: 'node.fault',
            style: {
                'background-color': '#7f1d1d',
                'border-color': '#ef4444',
                'border-width': 2,
                'color': '#f87171'
            }
        },
        {
            selector: 'node.initial',
            style: {
                'border-style': 'dashed'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': '#94a3b8',
                'target-arrow-color': '#94a3b8',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'label': 'data(label)',
                'font-size': '10px',
                'text-rotation': 'autorotate',
                'text-margin-y': -10,
                'text-background-color': '#ffffff',
                'text-background-opacity': 0.8,
                'text-background-padding': '2px',
                'color': '#475569'
            }
        }
    ];

    const handleNodeClick = (event) => {
        const node = event.target;
        if (onStateSelect) {
            onStateSelect(node.id());
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 flex flex-col h-full overflow-hidden">
            <div className="bg-gray-50 border-b border-gray-200 p-3 flex justify-between items-center">
                <h2 className="font-semibold text-gray-700 flex items-center gap-2">
                    State Machine Model
                </h2>
                <div className="flex gap-2 text-xs">
                    <span className="flex items-center gap-1"><div className="w-3 h-3 bg-blue-200 border-2 border-blue-500 rounded-sm"></div> Active</span>
                    <span className="flex items-center gap-1"><div className="w-3 h-3 bg-gray-200 border-2 border-red-500 rounded-sm"></div> Terminal</span>
                </div>
            </div>
            <div className="flex-grow relative bg-gray-50/50">
                {elements.length > 0 ? (
                    <CytoscapeComponent
                        elements={elements}
                        style={{ width: '100%', height: '100%' }}
                        stylesheet={style}
                        layout={{
                            name: 'dagre',
                            rankDir: 'TB',
                            nodeSep: 80,
                            rankSep: 100,
                            animate: true
                        }}
                        cy={(cy) => {
                            cy.on('tap', 'node', handleNodeClick);
                            // ensure it centers nicely on load
                            cy.fit();
                        }}
                    />
                ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-400">
                        No model loaded
                    </div>
                )}
            </div>
        </div>
    );
};

export default GraphPanel;
