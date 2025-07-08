# Streaming Transcription with MLX Whisper

## Overview

The streaming transcription feature provides faster transcription times by processing audio in overlapping chunks rather than waiting for the entire audio file to be processed. This approach can significantly reduce transcription time for longer audio files while maintaining accuracy.

## How It Works

### Chunking Strategy

The streaming backend splits audio into overlapping chunks:

- **Chunk Duration**: Default 10 seconds per chunk
- **Overlap Duration**: Default 2 seconds between chunks
- **Parallel Processing**: Multiple chunks processed simultaneously
- **Intelligent Merging**: Overlapping text is detected and removed

### Processing Pipeline

1. **Audio Loading**: Load the complete audio file
2. **Chunking**: Split into overlapping chunks
3. **Parallel Transcription**: Process chunks in parallel using ThreadPoolExecutor
4. **Result Merging**: Intelligently merge results, removing duplicates
5. **Performance Metrics**: Track timing and efficiency metrics

## Performance Benefits

### Theoretical Speedup

For a 109-second audio file:
- **Standard Approach**: Process entire file sequentially
- **Streaming Approach**: Process 10-second chunks in parallel

With 2 workers and 10-second chunks:
- Number of chunks: ~11 chunks
- Parallel processing: ~5-6 chunks processed simultaneously
- Expected speedup: 1.5-2x faster

### Real-world Considerations

- **Model Loading**: First chunk includes model loading time
- **Overhead**: Chunking and merging add some overhead
- **Memory Usage**: Multiple chunks in memory simultaneously
- **Accuracy**: Overlap helps maintain context and accuracy

## Configuration

### Backend Settings

```json
{
  "streaming_backend": {
    "enabled": true,
    "default_model": "large-v3-turbo",
    "chunk_duration": 10.0,
    "overlap_duration": 2.0,
    "max_workers": 2,
    "buffer_size": 5,
    "auto_cleanup": true
  }
}
```

### Performance Optimization

```json
{
  "performance_optimization": {
    "enable_parallel_processing": true,
    "enable_chunk_caching": false,
    "enable_result_caching": false,
    "min_chunk_duration": 5.0,
    "max_chunk_duration": 20.0,
    "optimal_overlap_ratio": 0.2
  }
}
```

## Usage

### In the Intake UI

1. Open the Intake UI
2. Go to Settings
3. Select "StreamingMLXWhisper" as the backend
4. Configure chunk duration and overlap as needed
5. Start recording

### Programmatic Usage

```python
from source.dictation_backends.streaming_mlx_whisper_backend import StreamingMLXWhisperBackend

# Create streaming backend
backend = StreamingMLXWhisperBackend(
    model_name="large-v3-turbo",
    chunk_duration=10.0,
    overlap_duration=2.0,
    max_workers=2
)

# Transcribe audio
result = backend.transcribe("audio_file.wav")

# Get performance metrics
metrics = backend.get_performance_metrics()
print(f"Speedup: {metrics['total_transcription_time']}")

# Clean up
backend.cleanup()
```

### Testing and Benchmarking

Use the test script to compare performance:

```bash
# Test streaming backend only
python scripts/test_streaming_transcription.py audio_file.wav

# Compare with standard backend
python scripts/test_streaming_transcription.py audio_file.wav --compare
```

## Optimization Strategies

### Chunk Size Optimization

- **Smaller chunks (5-8s)**: Faster processing, more overhead
- **Larger chunks (15-20s)**: Less overhead, slower processing
- **Optimal range**: 8-12 seconds for most use cases

### Overlap Optimization

- **Minimal overlap (1-2s)**: Faster processing, potential context loss
- **Generous overlap (3-4s)**: Better accuracy, more processing time
- **Optimal overlap**: 15-25% of chunk duration

### Worker Count Optimization

- **Single worker**: No parallelization, minimal memory usage
- **Multiple workers**: Better parallelization, higher memory usage
- **Optimal workers**: 2-4 for most systems

## Limitations and Considerations

### Memory Usage

- Multiple audio chunks loaded simultaneously
- Model weights shared across workers
- Temporary files for each chunk

### Accuracy Trade-offs

- Overlap regions may have slight inconsistencies
- Context boundaries between chunks
- Potential for duplicate text in overlap regions

### System Requirements

- Sufficient RAM for parallel processing
- Multi-core CPU for effective parallelization
- Fast storage for temporary files

## Troubleshooting

### Common Issues

1. **Out of Memory**: Reduce max_workers or chunk_duration
2. **Slow Performance**: Increase chunk_duration, reduce overlap
3. **Poor Accuracy**: Increase overlap_duration
4. **Model Loading Errors**: Ensure MLX Whisper is properly installed

### Performance Tuning

1. **Monitor metrics**: Use `get_performance_metrics()`
2. **Adjust chunk size**: Balance speed vs. overhead
3. **Optimize workers**: Match CPU cores available
4. **Test configurations**: Use the test script to find optimal settings

## Future Enhancements

### Planned Features

- **Real-time streaming**: Process audio as it's recorded
- **Adaptive chunking**: Adjust chunk size based on content
- **Advanced merging**: Use NLP techniques for better result merging
- **GPU optimization**: Better utilization of Metal acceleration

### Research Areas

- **Optimal chunk size algorithms**
- **Context preservation techniques**
- **Parallel processing optimization**
- **Memory usage optimization**

## References

- [MLX Whisper Documentation](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
- [Parallel Processing in Python](https://docs.python.org/3/library/concurrent.futures.html)
- [Audio Processing with SoundFile](https://pysoundfile.readthedocs.io/)
- [Performance Optimization Techniques](https://docs.python.org/3/library/profile.html) 