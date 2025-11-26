"""
Test script to demonstrate prompt hash functionality.
Run this to verify that different variations of the same prompt produce the same hash.
"""
import hashlib


def hash_prompt(prompt: str) -> str:
    """Create a hash of the prompt for consistent cache lookups."""
    normalized = ' '.join(prompt.strip().lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


if __name__ == "__main__":
    # Test cases - all should produce the same hash
    test_prompts = [
        "Summarize the document",
        "SUMMARIZE THE DOCUMENT",
        "  summarize   the   document  ",
        "Summarize    the    document",
        "summarize the document",
        "\tSummarize\tthe\tdocument\t",
    ]
    
    print("Testing prompt hash consistency:\n")
    print("-" * 80)
    
    hashes = {}
    for prompt in test_prompts:
        prompt_hash = hash_prompt(prompt)
        print(f"Prompt: '{prompt}'")
        print(f"Hash:   {prompt_hash}")
        print()
        
        if prompt_hash not in hashes:
            hashes[prompt_hash] = []
        hashes[prompt_hash].append(prompt)
    
    print("-" * 80)
    print(f"\nResult: All {len(test_prompts)} prompts produced {len(hashes)} unique hash(es)")
    
    if len(hashes) == 1:
        print("✓ SUCCESS: All variations produce the same hash!")
    else:
        print("✗ FAILURE: Different hashes produced")
        for hash_val, prompts in hashes.items():
            print(f"\nHash {hash_val}:")
            for p in prompts:
                print(f"  - '{p}'")
    
    # Test with example prompts from the UI
    print("\n" + "=" * 80)
    print("Testing example prompts from UI:\n")
    
    ui_prompts = [
        "Provide a comprehensive summary of this document, highlighting the main topics and key takeaways.",
        "Extract and list the key points, findings, or conclusions from this document.",
        "Identify and list all important entities mentioned in this document, including people, organizations, locations, and dates.",
    ]
    
    for prompt in ui_prompts:
        prompt_hash = hash_prompt(prompt)
        print(f"Prompt: {prompt[:60]}...")
        print(f"Hash:   {prompt_hash}\n")
