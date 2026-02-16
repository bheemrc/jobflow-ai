"""LeetCode practice tools: progress tracking, problem selection, attempt logging."""

from __future__ import annotations

import json

from langchain_core.tools import tool


@tool
def get_leetcode_progress() -> str:
    """Get the user's LeetCode practice progress.

    Returns JSON with solved count, streak, mastery by topic, recent problems.
    """
    # This returns mock data initially; real data comes from PostgreSQL via db.py
    return json.dumps({
        "total_solved": 0,
        "total_attempted": 0,
        "streak": 0,
        "problems": [],
        "mastery": [],
        "message": "No LeetCode data yet. Start practicing to track progress!",
    })


# Curated problem set by topic — covers all major interview patterns
PROBLEM_BANK = {
    "arrays": [
        {"id": 1, "title": "Two Sum", "difficulty": "easy", "pattern": "hash map", "url": "https://leetcode.com/problems/two-sum/"},
        {"id": 217, "title": "Contains Duplicate", "difficulty": "easy", "pattern": "hash set", "url": "https://leetcode.com/problems/contains-duplicate/"},
        {"id": 238, "title": "Product of Array Except Self", "difficulty": "medium", "pattern": "prefix sum", "url": "https://leetcode.com/problems/product-of-array-except-self/"},
        {"id": 15, "title": "3Sum", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/3sum/"},
        {"id": 11, "title": "Container With Most Water", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/container-with-most-water/"},
        {"id": 42, "title": "Trapping Rain Water", "difficulty": "hard", "pattern": "two pointers / stack", "url": "https://leetcode.com/problems/trapping-rain-water/"},
        {"id": 128, "title": "Longest Consecutive Sequence", "difficulty": "medium", "pattern": "hash set", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
        {"id": 41, "title": "First Missing Positive", "difficulty": "hard", "pattern": "cyclic sort", "url": "https://leetcode.com/problems/first-missing-positive/"},
    ],
    "sliding_window": [
        {"id": 121, "title": "Best Time to Buy and Sell Stock", "difficulty": "easy", "pattern": "sliding window", "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/"},
        {"id": 3, "title": "Longest Substring Without Repeating Characters", "difficulty": "medium", "pattern": "sliding window + hash", "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/"},
        {"id": 424, "title": "Longest Repeating Character Replacement", "difficulty": "medium", "pattern": "sliding window", "url": "https://leetcode.com/problems/longest-repeating-character-replacement/"},
        {"id": 76, "title": "Minimum Window Substring", "difficulty": "hard", "pattern": "sliding window + hash", "url": "https://leetcode.com/problems/minimum-window-substring/"},
        {"id": 239, "title": "Sliding Window Maximum", "difficulty": "hard", "pattern": "monotonic deque", "url": "https://leetcode.com/problems/sliding-window-maximum/"},
    ],
    "binary_search": [
        {"id": 704, "title": "Binary Search", "difficulty": "easy", "pattern": "binary search", "url": "https://leetcode.com/problems/binary-search/"},
        {"id": 33, "title": "Search in Rotated Sorted Array", "difficulty": "medium", "pattern": "modified binary search", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/"},
        {"id": 153, "title": "Find Minimum in Rotated Sorted Array", "difficulty": "medium", "pattern": "binary search", "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/"},
        {"id": 4, "title": "Median of Two Sorted Arrays", "difficulty": "hard", "pattern": "binary search", "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/"},
        {"id": 875, "title": "Koko Eating Bananas", "difficulty": "medium", "pattern": "binary search on answer", "url": "https://leetcode.com/problems/koko-eating-bananas/"},
    ],
    "linked_list": [
        {"id": 206, "title": "Reverse Linked List", "difficulty": "easy", "pattern": "in-place reversal", "url": "https://leetcode.com/problems/reverse-linked-list/"},
        {"id": 21, "title": "Merge Two Sorted Lists", "difficulty": "easy", "pattern": "merge", "url": "https://leetcode.com/problems/merge-two-sorted-lists/"},
        {"id": 141, "title": "Linked List Cycle", "difficulty": "easy", "pattern": "fast & slow pointers", "url": "https://leetcode.com/problems/linked-list-cycle/"},
        {"id": 143, "title": "Reorder List", "difficulty": "medium", "pattern": "fast & slow + reverse", "url": "https://leetcode.com/problems/reorder-list/"},
        {"id": 19, "title": "Remove Nth Node From End of List", "difficulty": "medium", "pattern": "two pointers", "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/"},
        {"id": 23, "title": "Merge k Sorted Lists", "difficulty": "hard", "pattern": "heap / divide & conquer", "url": "https://leetcode.com/problems/merge-k-sorted-lists/"},
        {"id": 138, "title": "Copy List with Random Pointer", "difficulty": "medium", "pattern": "hash map", "url": "https://leetcode.com/problems/copy-list-with-random-pointer/"},
    ],
    "trees": [
        {"id": 226, "title": "Invert Binary Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/invert-binary-tree/"},
        {"id": 104, "title": "Maximum Depth of Binary Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/"},
        {"id": 100, "title": "Same Tree", "difficulty": "easy", "pattern": "DFS", "url": "https://leetcode.com/problems/same-tree/"},
        {"id": 102, "title": "Binary Tree Level Order Traversal", "difficulty": "medium", "pattern": "BFS", "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/"},
        {"id": 98, "title": "Validate Binary Search Tree", "difficulty": "medium", "pattern": "DFS + range", "url": "https://leetcode.com/problems/validate-binary-search-tree/"},
        {"id": 236, "title": "Lowest Common Ancestor of a Binary Tree", "difficulty": "medium", "pattern": "DFS", "url": "https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-tree/"},
        {"id": 124, "title": "Binary Tree Maximum Path Sum", "difficulty": "hard", "pattern": "DFS + global max", "url": "https://leetcode.com/problems/binary-tree-maximum-path-sum/"},
        {"id": 297, "title": "Serialize and Deserialize Binary Tree", "difficulty": "hard", "pattern": "BFS / DFS", "url": "https://leetcode.com/problems/serialize-and-deserialize-binary-tree/"},
        {"id": 105, "title": "Construct Binary Tree from Preorder and Inorder Traversal", "difficulty": "medium", "pattern": "recursion + hash", "url": "https://leetcode.com/problems/construct-binary-tree-from-preorder-and-inorder-traversal/"},
    ],
    "graphs": [
        {"id": 200, "title": "Number of Islands", "difficulty": "medium", "pattern": "BFS / DFS", "url": "https://leetcode.com/problems/number-of-islands/"},
        {"id": 133, "title": "Clone Graph", "difficulty": "medium", "pattern": "BFS + hash", "url": "https://leetcode.com/problems/clone-graph/"},
        {"id": 207, "title": "Course Schedule", "difficulty": "medium", "pattern": "topological sort", "url": "https://leetcode.com/problems/course-schedule/"},
        {"id": 417, "title": "Pacific Atlantic Water Flow", "difficulty": "medium", "pattern": "multi-source BFS", "url": "https://leetcode.com/problems/pacific-atlantic-water-flow/"},
        {"id": 684, "title": "Redundant Connection", "difficulty": "medium", "pattern": "union find", "url": "https://leetcode.com/problems/redundant-connection/"},
        {"id": 743, "title": "Network Delay Time", "difficulty": "medium", "pattern": "Dijkstra", "url": "https://leetcode.com/problems/network-delay-time/"},
        {"id": 269, "title": "Alien Dictionary", "difficulty": "hard", "pattern": "topological sort", "url": "https://leetcode.com/problems/alien-dictionary/"},
        {"id": 787, "title": "Cheapest Flights Within K Stops", "difficulty": "medium", "pattern": "Bellman-Ford / BFS", "url": "https://leetcode.com/problems/cheapest-flights-within-k-stops/"},
    ],
    "dp": [
        {"id": 70, "title": "Climbing Stairs", "difficulty": "easy", "pattern": "1D DP", "url": "https://leetcode.com/problems/climbing-stairs/"},
        {"id": 198, "title": "House Robber", "difficulty": "medium", "pattern": "1D DP", "url": "https://leetcode.com/problems/house-robber/"},
        {"id": 322, "title": "Coin Change", "difficulty": "medium", "pattern": "unbounded knapsack", "url": "https://leetcode.com/problems/coin-change/"},
        {"id": 300, "title": "Longest Increasing Subsequence", "difficulty": "medium", "pattern": "1D DP + binary search", "url": "https://leetcode.com/problems/longest-increasing-subsequence/"},
        {"id": 1143, "title": "Longest Common Subsequence", "difficulty": "medium", "pattern": "2D DP", "url": "https://leetcode.com/problems/longest-common-subsequence/"},
        {"id": 518, "title": "Coin Change II", "difficulty": "medium", "pattern": "unbounded knapsack", "url": "https://leetcode.com/problems/coin-change-ii/"},
        {"id": 72, "title": "Edit Distance", "difficulty": "medium", "pattern": "2D DP", "url": "https://leetcode.com/problems/edit-distance/"},
        {"id": 312, "title": "Burst Balloons", "difficulty": "hard", "pattern": "interval DP", "url": "https://leetcode.com/problems/burst-balloons/"},
        {"id": 10, "title": "Regular Expression Matching", "difficulty": "hard", "pattern": "2D DP", "url": "https://leetcode.com/problems/regular-expression-matching/"},
        {"id": 152, "title": "Maximum Product Subarray", "difficulty": "medium", "pattern": "DP with min/max", "url": "https://leetcode.com/problems/maximum-product-subarray/"},
    ],
    "strings": [
        {"id": 242, "title": "Valid Anagram", "difficulty": "easy", "pattern": "hash map / sort", "url": "https://leetcode.com/problems/valid-anagram/"},
        {"id": 49, "title": "Group Anagrams", "difficulty": "medium", "pattern": "hash map", "url": "https://leetcode.com/problems/group-anagrams/"},
        {"id": 20, "title": "Valid Parentheses", "difficulty": "easy", "pattern": "stack", "url": "https://leetcode.com/problems/valid-parentheses/"},
        {"id": 5, "title": "Longest Palindromic Substring", "difficulty": "medium", "pattern": "expand from center / DP", "url": "https://leetcode.com/problems/longest-palindromic-substring/"},
        {"id": 647, "title": "Palindromic Substrings", "difficulty": "medium", "pattern": "expand from center", "url": "https://leetcode.com/problems/palindromic-substrings/"},
        {"id": 271, "title": "Encode and Decode Strings", "difficulty": "medium", "pattern": "design", "url": "https://leetcode.com/problems/encode-and-decode-strings/"},
    ],
    "heap": [
        {"id": 703, "title": "Kth Largest Element in a Stream", "difficulty": "easy", "pattern": "min heap", "url": "https://leetcode.com/problems/kth-largest-element-in-a-stream/"},
        {"id": 215, "title": "Kth Largest Element in an Array", "difficulty": "medium", "pattern": "quickselect / heap", "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/"},
        {"id": 347, "title": "Top K Frequent Elements", "difficulty": "medium", "pattern": "heap / bucket sort", "url": "https://leetcode.com/problems/top-k-frequent-elements/"},
        {"id": 295, "title": "Find Median from Data Stream", "difficulty": "hard", "pattern": "two heaps", "url": "https://leetcode.com/problems/find-median-from-data-stream/"},
        {"id": 621, "title": "Task Scheduler", "difficulty": "medium", "pattern": "greedy / heap", "url": "https://leetcode.com/problems/task-scheduler/"},
    ],
    "backtracking": [
        {"id": 78, "title": "Subsets", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/subsets/"},
        {"id": 46, "title": "Permutations", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/permutations/"},
        {"id": 39, "title": "Combination Sum", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/combination-sum/"},
        {"id": 79, "title": "Word Search", "difficulty": "medium", "pattern": "backtracking + DFS", "url": "https://leetcode.com/problems/word-search/"},
        {"id": 51, "title": "N-Queens", "difficulty": "hard", "pattern": "backtracking", "url": "https://leetcode.com/problems/n-queens/"},
        {"id": 131, "title": "Palindrome Partitioning", "difficulty": "medium", "pattern": "backtracking", "url": "https://leetcode.com/problems/palindrome-partitioning/"},
    ],
    "greedy": [
        {"id": 55, "title": "Jump Game", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/jump-game/"},
        {"id": 45, "title": "Jump Game II", "difficulty": "medium", "pattern": "greedy BFS", "url": "https://leetcode.com/problems/jump-game-ii/"},
        {"id": 134, "title": "Gas Station", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/gas-station/"},
        {"id": 846, "title": "Hand of Straights", "difficulty": "medium", "pattern": "greedy + hash", "url": "https://leetcode.com/problems/hand-of-straights/"},
        {"id": 763, "title": "Partition Labels", "difficulty": "medium", "pattern": "greedy", "url": "https://leetcode.com/problems/partition-labels/"},
    ],
    "intervals": [
        {"id": 57, "title": "Insert Interval", "difficulty": "medium", "pattern": "intervals", "url": "https://leetcode.com/problems/insert-interval/"},
        {"id": 56, "title": "Merge Intervals", "difficulty": "medium", "pattern": "sort + merge", "url": "https://leetcode.com/problems/merge-intervals/"},
        {"id": 435, "title": "Non-overlapping Intervals", "difficulty": "medium", "pattern": "greedy intervals", "url": "https://leetcode.com/problems/non-overlapping-intervals/"},
        {"id": 252, "title": "Meeting Rooms", "difficulty": "easy", "pattern": "sort", "url": "https://leetcode.com/problems/meeting-rooms/"},
        {"id": 253, "title": "Meeting Rooms II", "difficulty": "medium", "pattern": "heap / sweep line", "url": "https://leetcode.com/problems/meeting-rooms-ii/"},
    ],
    "stack": [
        {"id": 155, "title": "Min Stack", "difficulty": "medium", "pattern": "stack design", "url": "https://leetcode.com/problems/min-stack/"},
        {"id": 150, "title": "Evaluate Reverse Polish Notation", "difficulty": "medium", "pattern": "stack", "url": "https://leetcode.com/problems/evaluate-reverse-polish-notation/"},
        {"id": 739, "title": "Daily Temperatures", "difficulty": "medium", "pattern": "monotonic stack", "url": "https://leetcode.com/problems/daily-temperatures/"},
        {"id": 84, "title": "Largest Rectangle in Histogram", "difficulty": "hard", "pattern": "monotonic stack", "url": "https://leetcode.com/problems/largest-rectangle-in-histogram/"},
        {"id": 853, "title": "Car Fleet", "difficulty": "medium", "pattern": "stack + sort", "url": "https://leetcode.com/problems/car-fleet/"},
    ],
    "trie": [
        {"id": 208, "title": "Implement Trie (Prefix Tree)", "difficulty": "medium", "pattern": "trie", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/"},
        {"id": 211, "title": "Design Add and Search Words Data Structure", "difficulty": "medium", "pattern": "trie + DFS", "url": "https://leetcode.com/problems/design-add-and-search-words-data-structure/"},
        {"id": 212, "title": "Word Search II", "difficulty": "hard", "pattern": "trie + backtracking", "url": "https://leetcode.com/problems/word-search-ii/"},
    ],
    "union_find": [
        {"id": 323, "title": "Number of Connected Components in an Undirected Graph", "difficulty": "medium", "pattern": "union find", "url": "https://leetcode.com/problems/number-of-connected-components-in-an-undirected-graph/"},
        {"id": 128, "title": "Longest Consecutive Sequence", "difficulty": "medium", "pattern": "union find / hash set", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
        {"id": 305, "title": "Number of Islands II", "difficulty": "hard", "pattern": "union find", "url": "https://leetcode.com/problems/number-of-islands-ii/"},
    ],
    "bit_manipulation": [
        {"id": 136, "title": "Single Number", "difficulty": "easy", "pattern": "XOR", "url": "https://leetcode.com/problems/single-number/"},
        {"id": 191, "title": "Number of 1 Bits", "difficulty": "easy", "pattern": "bit counting", "url": "https://leetcode.com/problems/number-of-1-bits/"},
        {"id": 338, "title": "Counting Bits", "difficulty": "easy", "pattern": "DP + bits", "url": "https://leetcode.com/problems/counting-bits/"},
        {"id": 371, "title": "Sum of Two Integers", "difficulty": "medium", "pattern": "bit manipulation", "url": "https://leetcode.com/problems/sum-of-two-integers/"},
    ],
    "math": [
        {"id": 48, "title": "Rotate Image", "difficulty": "medium", "pattern": "matrix", "url": "https://leetcode.com/problems/rotate-image/"},
        {"id": 54, "title": "Spiral Matrix", "difficulty": "medium", "pattern": "matrix", "url": "https://leetcode.com/problems/spiral-matrix/"},
        {"id": 73, "title": "Set Matrix Zeroes", "difficulty": "medium", "pattern": "matrix in-place", "url": "https://leetcode.com/problems/set-matrix-zeroes/"},
        {"id": 202, "title": "Happy Number", "difficulty": "easy", "pattern": "fast & slow", "url": "https://leetcode.com/problems/happy-number/"},
        {"id": 50, "title": "Pow(x, n)", "difficulty": "medium", "pattern": "fast exponentiation", "url": "https://leetcode.com/problems/powx-n/"},
    ],
    "design": [
        {"id": 146, "title": "LRU Cache", "difficulty": "medium", "pattern": "hash map + doubly linked list", "url": "https://leetcode.com/problems/lru-cache/"},
        {"id": 460, "title": "LFU Cache", "difficulty": "hard", "pattern": "hash map + doubly linked list", "url": "https://leetcode.com/problems/lfu-cache/"},
        {"id": 380, "title": "Insert Delete GetRandom O(1)", "difficulty": "medium", "pattern": "hash map + array", "url": "https://leetcode.com/problems/insert-delete-getrandom-o1/"},
        {"id": 355, "title": "Design Twitter", "difficulty": "medium", "pattern": "heap + hash map", "url": "https://leetcode.com/problems/design-twitter/"},
    ],
}


@tool
def select_leetcode_problems(topics: str = "arrays,dp", difficulty: str = "medium", count: int = 3) -> str:
    """Select LeetCode problems for practice based on weak topics.

    Args:
        topics: Comma-separated topics to practice (e.g., "graphs,dp").
        difficulty: easy, medium, or hard.
        count: Number of problems to select.

    Returns:
        JSON with selected problems.
    """
    topic_list = [t.strip().lower() for t in topics.split(",")]
    selected = []
    for topic in topic_list:
        problems = PROBLEM_BANK.get(topic, [])
        filtered = [p for p in problems if p["difficulty"] == difficulty] or problems
        selected.extend(filtered[:count])

    available_topics = sorted(PROBLEM_BANK.keys())

    return json.dumps({
        "topics": topic_list,
        "difficulty": difficulty,
        "total_in_bank": sum(len(v) for v in PROBLEM_BANK.values()),
        "available_topics": available_topics,
        "problems": selected[:count],
    })


@tool
def log_leetcode_attempt_tool(problem_id: int, solved: bool, time_minutes: int = 0) -> str:
    """Log a LeetCode problem attempt.

    Args:
        problem_id: The LeetCode problem number.
        solved: Whether the user solved it.
        time_minutes: Time spent in minutes.

    Returns:
        Confirmation message.
    """
    return json.dumps({
        "logged": True,
        "problem_id": problem_id,
        "solved": solved,
        "time_minutes": time_minutes,
        "message": f"Logged attempt for problem {problem_id}. {'Solved!' if solved else 'Keep practicing!'}",
    })
