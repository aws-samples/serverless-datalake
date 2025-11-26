import { useState } from 'react';
import {
  FormField,
  Textarea,
  Button,
  SpaceBetween,
  Select,
} from '@cloudscape-design/components';
import type { SelectProps } from '@cloudscape-design/components';

interface PromptInputProps {
  onSubmit: (prompt: string) => void;
  loading?: boolean;
  disabled?: boolean;
}

const EXAMPLE_PROMPTS: SelectProps.Option[] = [
  {
    label: 'Summarize the document',
    value: 'Provide a comprehensive summary of this document, highlighting the main topics and key takeaways.',
  },
  {
    label: 'Extract key points',
    value: 'Extract and list the key points, findings, or conclusions from this document.',
  },
  {
    label: 'Identify entities',
    value: 'Identify and list all important entities mentioned in this document, including people, organizations, locations, and dates.',
  },
  {
    label: 'Extract action items',
    value: 'Extract all action items, tasks, or recommendations mentioned in this document.',
  },
  {
    label: 'Analyze sentiment',
    value: 'Analyze the overall sentiment and tone of this document. Is it positive, negative, or neutral?',
  },
  {
    label: 'Extract statistics',
    value: 'Extract all numerical data, statistics, and metrics mentioned in this document.',
  },
];

export const PromptInput: React.FC<PromptInputProps> = ({
  onSubmit,
  loading = false,
  disabled = false,
}) => {
  const [prompt, setPrompt] = useState('');
  const [selectedExample, setSelectedExample] = useState<SelectProps.Option | null>(null);
  const [error, setError] = useState<string | null>(null);

  const MAX_LENGTH = 1000;

  const handlePromptChange = (value: string) => {
    if (value.length <= MAX_LENGTH) {
      setPrompt(value);
      setError(null);
    }
  };

  const handleExampleSelect = (option: SelectProps.Option | null) => {
    setSelectedExample(option);
    if (option && option.value) {
      setPrompt(option.value);
      setError(null);
    }
  };

  const handleSubmit = () => {
    // Validate prompt
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    if (prompt.length > MAX_LENGTH) {
      setError(`Prompt must be ${MAX_LENGTH} characters or less`);
      return;
    }

    setError(null);
    onSubmit(prompt.trim());
  };

  const handleKeyPress = (event: any) => {
    // Submit on Ctrl+Enter or Cmd+Enter
    if ((event.detail?.ctrlKey || event.detail?.metaKey) && event.detail?.key === 'Enter') {
      handleSubmit();
    }
  };

  return (
    <SpaceBetween size="m">
      <FormField
        label="Example Prompts"
        description="Select an example prompt or write your own"
      >
        <Select
          selectedOption={selectedExample}
          onChange={({ detail }) => handleExampleSelect(detail.selectedOption)}
          options={EXAMPLE_PROMPTS}
          placeholder="Choose an example prompt (optional)"
          disabled={disabled || loading}
        />
      </FormField>

      <FormField
        label="Your Prompt"
        description={`Enter a natural language prompt to extract insights from the document (${prompt.length}/${MAX_LENGTH} characters)`}
        errorText={error}
      >
        <Textarea
          value={prompt}
          onChange={({ detail }) => handlePromptChange(detail.value)}
          placeholder="e.g., Summarize the main findings and recommendations from this document"
          rows={6}
          disabled={disabled || loading}
          onKeyDown={handleKeyPress}
        />
      </FormField>

      <Button
        variant="primary"
        onClick={handleSubmit}
        loading={loading}
        disabled={disabled || !prompt.trim()}
      >
        {loading ? 'Extracting Insights...' : 'Extract Insights'}
      </Button>

      <div style={{ fontSize: '12px', color: '#5f6b7a' }}>
        Tip: Press Ctrl+Enter (Cmd+Enter on Mac) to submit
      </div>
    </SpaceBetween>
  );
};
