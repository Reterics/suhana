import { useState } from 'preact/hooks';
import { ChevronDown, ChevronRight, Code } from 'lucide-preact';

interface ProjectMetadataProps {
  metadata: any;
}

export function ProjectMetadata({ metadata }: ProjectMetadataProps) {
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});

  if (!metadata) {
    return null;
  }

  const toggleExpanded = (key: string) => {
    setExpandedKeys(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Format a metadata value for display
  const formatValue = (value: any): string => {
    if (typeof value === 'string') {
      return value;
    }
    if (Array.isArray(value)) {
      return `[${value.length} items]`;
    }
    if (typeof value === 'object' && value !== null) {
      return '{...}';
    }
    return String(value);
  };

  const renderNestedValue = (key: string, value: any) => {
    if (Array.isArray(value)) {
      return (
        <div className="ml-4 mt-1" key={key}>
          {value.map((item, index) => (
            <div key={index} className="text-xs text-gray-600 py-0.5">
              {typeof item === 'object' ? JSON.stringify(item) : String(item)}
            </div>
          ))}
        </div>
      );
    }

    if (typeof value === 'object' && value !== null) {
      return (
        <div className="ml-4 mt-1" key={key}>
          {Object.entries(value).map(([nestedKey, nestedValue]) => (
            <div key={nestedKey} className="text-xs text-gray-600 py-0.5">
              <span className="font-medium">{nestedKey}:</span>{' '}
              {typeof nestedValue === 'object'
                ? JSON.stringify(nestedValue)
                : String(nestedValue)}
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="overflow-hidden">
      {Object.entries(metadata)
        .filter(([key]) => key !== 'name') // Skip name as it's already in the header
        .map(([key, value]) => (
          <div key={key} className="mb-3">
            <div
              className="flex items-center justify-between cursor-pointer hover:bg-gray-50 p-1 rounded"
              onClick={() => (Array.isArray(value) || (typeof value === 'object' && value !== null)) ? toggleExpanded(key) : null}
            >
              <div className="flex items-center gap-1">
                <Code className="h-3 w-3 text-gray-400" />
                <span className="text-xs font-medium text-gray-700">{key}:</span>
                <span className="text-xs text-gray-600">
                  {formatValue(value)}
                </span>
              </div>
              {(Array.isArray(value) || (typeof value === 'object' && value !== null)) && (
                expandedKeys[key] ? (
                  <ChevronDown className="h-3 w-3 text-gray-500" />
                ) : (
                  <ChevronRight className="h-3 w-3 text-gray-500" />
                )
              )}
            </div>
            {expandedKeys[key] && (Array.isArray(value) || (typeof value === 'object' && value !== null)) &&
              renderNestedValue(key, value)}
          </div>
        ))}
    </div>
  );
}
