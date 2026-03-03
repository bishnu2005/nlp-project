import React from 'react';

const SourcePanel = ({ sourceSentences, selectedStateId }) => {
    if (!selectedStateId) {
        return (
            <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4 h-full flex flex-col items-center justify-center text-gray-400 text-sm">
                <p>Select a state to view traceability.</p>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 flex flex-col h-full overflow-hidden">
            <div className="bg-gray-50 border-b border-gray-200 p-3 flex justify-between items-center">
                <h2 className="font-semibold text-gray-700 text-sm">Source Traceability</h2>
                <span className="text-xs bg-gray-200 text-gray-700 px-2 py-0.5 rounded-full font-mono">{selectedStateId}</span>
            </div>
            <div className="flex-grow p-4 overflow-y-auto">
                {sourceSentences.length > 0 ? (
                    <div className="space-y-4">
                        <p className="text-sm text-gray-500 mb-2">Sentences responsible for generating this state and its transitions:</p>
                        {sourceSentences.map((sentence, idx) => {
                            // Extract ID like [s001]
                            const match = sentence.match(/^\[(.*?)\]\s*(.*)$/);
                            if (match) {
                                return (
                                    <div key={idx} className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-md">
                                        <span className="text-xs font-bold font-mono text-yellow-800 bg-yellow-200 px-1 py-0.5 rounded mr-2">
                                            {match[1]}
                                        </span>
                                        <span className="text-gray-800 text-sm">{match[2]}</span>
                                    </div>
                                );
                            }
                            return (
                                <div key={idx} className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-md text-sm text-gray-800">
                                    {sentence}
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-sm text-gray-500 italic p-4 text-center">
                        No source sentences linked to this state.
                    </div>
                )}
            </div>
        </div>
    );
};

export default SourcePanel;
