#!/usr/bin/env python3
"""Benchmark script to measure j2toon performance."""

import time
import sys
from j2toon import json2toon, toon2json


def benchmark_encoding(data, iterations=1000):
    """Benchmark encoding performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        json2toon(data)
    end = time.perf_counter()
    return (end - start) / iterations * 1000  # ms per iteration


def benchmark_decoding(text, iterations=1000):
    """Benchmark decoding performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        toon2json(text)
    end = time.perf_counter()
    return (end - start) / iterations * 1000  # ms per iteration


def main():
    """Run benchmarks on various data types."""
    print("j2toon Performance Benchmarks")
    print("=" * 60)
    
    # Benchmark 1: Simple object
    simple_data = {"name": "Alice", "age": 30, "active": True}
    simple_time = benchmark_encoding(simple_data)
    print(f"\n1. Simple Object (3 fields)")
    print(f"   Encoding: {simple_time:.4f} ms/op")
    
    simple_toon = json2toon(simple_data)
    simple_decode_time = benchmark_decoding(simple_toon)
    print(f"   Decoding: {simple_decode_time:.4f} ms/op")
    
    # Benchmark 2: Tabular data
    tabular_data = {
        "users": [
            {"id": i, "name": f"User{i}", "score": i * 10.5}
            for i in range(20)
        ]
    }
    tabular_time = benchmark_encoding(tabular_data, iterations=500)
    print(f"\n2. Tabular Data (20 rows, 3 columns)")
    print(f"   Encoding: {tabular_time:.4f} ms/op")
    
    tabular_toon = json2toon(tabular_data)
    tabular_decode_time = benchmark_decoding(tabular_toon, iterations=500)
    print(f"   Decoding: {tabular_decode_time:.4f} ms/op")
    
    # Benchmark 3: Deep nesting
    deep_data = {"level1": {"level2": {"level3": {"level4": {"level5": {
        "value": "deep",
        "numbers": list(range(10)),
        "metadata": {"type": "test", "version": 1}
    }}}}}}
    deep_time = benchmark_encoding(deep_data)
    print(f"\n3. Deep Nesting (5 levels)")
    print(f"   Encoding: {deep_time:.4f} ms/op")
    
    deep_toon = json2toon(deep_data)
    deep_decode_time = benchmark_decoding(deep_toon)
    print(f"   Decoding: {deep_decode_time:.4f} ms/op")
    
    # Benchmark 4: Large array
    large_array = {"items": list(range(100))}
    large_time = benchmark_encoding(large_array, iterations=500)
    print(f"\n4. Large Array (100 elements)")
    print(f"   Encoding: {large_time:.4f} ms/op")
    
    large_toon = json2toon(large_array)
    large_decode_time = benchmark_decoding(large_toon, iterations=500)
    print(f"   Decoding: {large_decode_time:.4f} ms/op")
    
    # Benchmark 5: Mixed data
    mixed_data = {
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "profile": {
                    "age": 20 + i,
                    "active": i % 2 == 0,
                },
                "tags": ["tag1", "tag2", "tag3"],
            }
            for i in range(10)
        ],
        "metadata": {
            "count": 10,
            "timestamp": 1234567890,
            "source": "benchmark",
        },
    }
    mixed_time = benchmark_encoding(mixed_data, iterations=200)
    print(f"\n5. Complex Mixed Data (10 nested objects)")
    print(f"   Encoding: {mixed_time:.4f} ms/op")
    
    mixed_toon = json2toon(mixed_data)
    mixed_decode_time = benchmark_decoding(mixed_toon, iterations=200)
    print(f"   Decoding: {mixed_decode_time:.4f} ms/op")
    
    print("\n" + "=" * 60)
    print("Benchmark complete!")
    
    # Calculate averages
    avg_encode = (simple_time + tabular_time + deep_time + large_time + mixed_time) / 5
    avg_decode = (simple_decode_time + tabular_decode_time + deep_decode_time + 
                  large_decode_time + mixed_decode_time) / 5
    print(f"\nAverage encoding time: {avg_encode:.4f} ms/op")
    print(f"Average decoding time: {avg_decode:.4f} ms/op")
    print(f"Total round-trip time: {avg_encode + avg_decode:.4f} ms/op")


if __name__ == "__main__":
    main()
