#!/usr/bin/env python3
"""
Token Guardian 225-Query Shadow Test
Runs comprehensive classification test and reports metrics
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.core.classifier import Classifier
from src.core.pipeline import create_pipeline


# Comprehensive test query set (225 queries across categories)
TEST_QUERIES = [
    # CODING (35 queries)
    "Write a Python function to sort arrays",
    "Create a REST API endpoint in Node.js",
    "Debug this JavaScript code",
    "Write a SQL query to join tables",
    "Implement a binary search algorithm",
    "Create a React component for user login",
    "Write a bash script to backup files",
    "Build a Python class for database connections",
    "Debug memory leak in C++ application",
    "Write unit tests for this function",
    "Refactor this spaghetti code",
    "Create a microservice in Go",
    "Write a regex to validate email",
    "Build a GraphQL resolver",
    "Implement authentication middleware",
    "Create a Docker container for this app",
    "Write a Python script to scrape websites",
    "Debug why this API returns 500",
    "Create a CLI tool in Rust",
    "Write unit tests for authentication module",
    "Build a web scraper in Python",
    "Implement file upload handler",
    "Write a cron job to clean logs",
    "Create a blockchain smart contract",
    "Debug race condition in concurrent code",
    "Build a real-time chat app",
    "Write database migration script",
    "Implement rate limiter middleware",
    "Create a payment integration",
    "Write code documentation",
    "Build a file processing pipeline",
    "Debug circular dependency issue",
    "Create an API gateway service",
    "Write a background worker task",
    
    # DATA ANALYSIS (30 queries)
    "Analyze sales data from last quarter",
    "Create a chart showing monthly trends",
    "Summarize customer feedback data",
    "Find patterns in user behavior",
    "Generate a report on website traffic",
    "Analyze A/B test results",
    "Calculate average order value",
    "Create a pivot table in Excel",
    "Find correlations in this dataset",
    "Visualize population growth over time",
    "Generate quarterly business report",
    "Analyze customer churn rate",
    "Find top-selling products",
    "Create a dashboard for KPIs",
    "Analyze social media engagement",
    "Calculate conversion rates",
    "Find anomalies in transaction data",
    "Generate market analysis report",
    "Analyze inventory turnover",
    "Create a heatmap of user activity",
    "Calculate customer lifetime value",
    "Analyze competitor pricing data",
    "Find seasonal trends in sales",
    "Generate lead scoring model",
    "Analyze support ticket categories",
    "Calculate return on investment",
    "Create a forecast for next quarter",
    "Analyze user session duration",
    "Find most profitable customer segments",
    "Generate performance metrics report",
    
    # CREATIVE (30 queries)
    "Write a creative story about space",
    "Write a poem about autumn",
    "Create a blog post about productivity",
    "Write a short story with a twist ending",
    "Design a marketing tagline",
    "Write a script for a YouTube video",
    "Create character descriptions for a novel",
    "Write a dialogue between two characters",
    "Design a brand name and slogan",
    "Write a limerick about programming",
    "Create a children's story",
    "Write a motivational speech",
    "Design a logo description",
    "Write a flash fiction piece",
    "Create a podcast outline",
    "Write a news article style piece",
    "Design a social media campaign",
    "Write a book review",
    "Create a travel blog post",
    "Write a haiku collection",
    "Design a movie pitch",
    "Write a personal essay",
    "Create a cooking recipe with story",
    "Write a speech for graduation",
    "Design a video game character",
    "Write a romance short story",
    "Create a product description",
    "Write a satire piece",
    "Design a comic strip script",
    "Write a mystery story opening",
    
    # REASONING (40 queries)
    "Explain why the sky is blue",
    "Compare REST vs GraphQL",
    "Pros and cons of AI",
    "Step by step guide to cooking",
    "Why does gravity exist",
    "Explain how photosynthesis works",
    "Compare monarchy vs democracy",
    "What are the tradeoffs of remote work",
    "Explain the cause of climate change",
    "Walk me through the hiring process",
    "Why do we dream when sleeping",
    "Compare iOS vs Android",
    "What are the differences between stocks and bonds",
    "Explain the reasoning behind this decision",
    "Why is coffee addictive",
    "Step by step to start a business",
    "Explain the impact of social media",
    "What caused World War I",
    "Compare Python vs JavaScript",
    "Why should we learn history",
    "Walk me through solving this equation",
    "What are the effects of sleep deprivation",
    "Explain why democracy is important",
    "Compare laptop vs desktop for work",
    "What are the benefits of meditation",
    "Explain how vaccines work",
    "Why do cats land on their feet",
    "Compare traditional vs renewable energy",
    "What are the long-term effects of smoking",
    "Explain the reasoning for this policy",
    "Step by step to plan a wedding",
    "Why do we have seasons",
    "Compare streaming vs cable TV",
    "What are the pros and cons of colonization",
    "Explain why languages evolve",
    "Step by step to build a house",
    "What caused the Great Depression",
    "Compare capitalism and socialism",
    "Explain how the stock market works",
    
    # SIMPLE QA (60 queries)
    "What is machine learning",
    "What time is it in Tokyo",
    "What is the capital of France",
    "When was Python invented",
    "What is 2+2",
    "Who invented the telephone",
    "What is the population of Earth",
    "What year did World War II end",
    "What is the boiling point of water",
    "Where is the Eiffel Tower located",
    "What does API stand for",
    "What is the largest planet",
    "Who wrote Romeo and Juliet",
    "What is 15% tip on 50 dollars",
    "What temperature does ice melt",
    "What is the currency of Japan",
    "When is summer solstice",
    "What is the speed of light",
    "What is a compiler",
    "Who painted Mona Lisa",
    "What is DNA made of",
    "Where is Amazon headquarters",
    "What does HTML stand for",
    "What is the tallest mountain",
    "Who invented light bulb",
    "What is 100 Fahrenheit in Celsius",
    "What is the capital of Brazil",
    "When was internet invented",
    "What is Git version control",
    "What is the largest ocean",
    "Who discovered penicillin",
    "What does CPU stand for",
    "What is the smallest country",
    "Where is Mount Everest",
    "What is blockchain technology",
    "Who invented World Wide Web",
    "What is the currency of UK",
    "What is the main ingredient in bread",
    "When does the sun set today",
    "What is 20% of 150",
    "What does GPU stand for",
    "What is the longest river",
    "Who invented the wheel",
    "What is HTTPS protocol",
    "What is the capital of Australia",
    "When was the Constitution written",
    "What is artificial intelligence",
    "What is the freezing point of water",
    "Where is the Great Barrier Reef",
    "Who invented dynamite",
    "What is the primary key in database",
    "What is the largest mammal",
    "What currency is used in Germany",
    "When is New Year's Day",
    "What is HTTP request",
    "What is the deepest ocean",
    "Who invented printing press",
    "What is DNS in networking",
    "What is the capital of Canada",
    "What is the speed of sound",
    
    # VAGUE/EDGE (30 queries)
    "General question about AI",
    "Tell me about technology",
    "Something about programming",
    "Discuss the future",
    "What do you think about everything",
    "Give me information",
    "I have a question",
    "Tell me stuff",
    "Explain something",
    "Discuss topic",
    "General knowledge question",
    "Question about life",
    "Tell me about the world",
    "I want to know things",
    "General inquiry",
    "Give me facts",
    "Question regarding stuff",
    "Explain the concept",
    "Talk about anything",
    "I need information",
    "What should I know",
    "General discussion",
    "Tell me more",
    "Explain it all",
    "General query",
    "Facts about things",
    "Question about topic",
    "Tell me everything",
    "I wonder about stuff",
    "Explain various things",
]


def run_test():
    """Run the 225-query shadow test"""
    print("=" * 80)
    print("TOKEN GUARDIAN 225-QUERY SHADOW TEST")
    print("=" * 80)
    print()
    
    pipeline = create_pipeline(shadow_mode=True)
    classifier = Classifier()
    
    # Track metrics
    label_counts = defaultdict(int)
    fallback_reasons = defaultdict(int)
    confidence_buckets = {"<0.60": 0, "0.60-0.79": 0, ">=0.80": 0}
    fallback_count = 0
    decisions = []
    reasoning_floored = []
    moved_from_fallback = []
    
    for query in TEST_QUERIES:
        decision = pipeline.process(query)
        decisions.append(decision)
        
        # Label breakdown
        label_counts[decision.classification] += 1
        
        # Fallback tracking
        if decision.fallback_triggered:
            fallback_count += 1
            # Extract fallback reason
            reason = decision.fallback_reason.split(":")[0] if decision.fallback_reason else "UNKNOWN"
            fallback_reasons[reason] += 1
        
        # Track queries routing to preferred model with conf < 0.80 (LOW-band impact)
        if decision.confidence < 0.80:
            preferred = classifier.get_preferred_model(decision.classification)
            if decision.selected_model == preferred:
                moved_from_fallback.append({
                    "query": query[:50],
                    "label": decision.classification,
                    "confidence": decision.confidence,
                    "model": decision.selected_model,
                    "reason": decision.fallback_reason.split(":")[0] if decision.fallback_reason else ""
                })
        
        # Confidence bucket
        if decision.confidence < 0.60:
            confidence_buckets["<0.60"] += 1
        elif decision.confidence < 0.80:
            confidence_buckets["0.60-0.79"] += 1
        else:
            confidence_buckets[">=0.80"] += 1
        
        # Track reasoning floor impact
        if decision.classification == "reasoning":
            reasoning_floored.append({
                "query": query[:50],
                "confidence": decision.confidence,
                "fallback": decision.fallback_triggered,
                "reason": decision.fallback_reason
            })
    
    # Calculate metrics
    total = len(TEST_QUERIES)
    fallback_rate = (fallback_count / total) * 100
    
    # Report
    print(f"Total Queries: {total}")
    print(f"Fallacks: {fallback_count} ({fallback_rate:.1f}%)")
    print()
    
    print("-" * 40)
    print("BREAKDOWN BY LABEL")
    print("-" * 40)
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {label:18}: {count:3} ({count/total*100:.1f}%)")
    
    print()
    print("-" * 40)
    print("BREAKDOWN BY FALLBACK REASON")
    print("-" * 40)
    for reason, count in sorted(fallback_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:30}: {count}")
    
    print()
    print("-" * 40)
    print("CONFIDENCE HISTOGRAM")
    print("-" * 40)
    for bucket, count in confidence_buckets.items():
        bar = "█" * (count // 2)
        print(f"  {bucket:12}: {count:3} ({count/total*100:.1f}%) {bar}")
    
    print()
    print("-" * 40)
    print("REASONING FLOOR IMPACT")
    print("-" * 40)
    reasoning_count = label_counts.get("reasoning", 0)
    floored = sum(1 for r in reasoning_floored if r["confidence"] >= 0.80)
    print(f"  Total reasoning queries: {reasoning_count}")
    print(f"  Floored to >=0.80: {floored} ({floored/reasoning_count*100:.1f}%)")
    
    if reasoning_floored:
        print()
        print("  Sample floored queries:")
        for r in reasoning_floored[:5]:
            fb = "FALLBACK" if r["fallback"] else "OK"
            print(f"    [{fb}] {r['query']:45} conf={r['confidence']:.2f}")
    
    print()
    print("-" * 40)
    print("LOW-BAND ROUTES PREVENTING FALLBACK")
    print("-" * 40)
    print(f"  Queries routing to preferred model with conf < 0.80: {len(moved_from_fallback)}")
    
    if moved_from_fallback:
        # Group by reason
        by_reason = defaultdict(list)
        for m in moved_from_fallback:
            by_reason[m["reason"]].append(m)
        
        for reason, items in sorted(by_reason.items(), key=lambda x: -len(x[1])):
            print(f"\n  {reason}: {len(items)} queries")
            for item in items[:10]:
                print(f"    [{item['label']:14}] conf={item['confidence']:.2f} → {item['model']:20} | {item['query']}")
    
    # Save results
    results = {
        "total": total,
        "fallback_count": fallback_count,
        "fallback_rate": fallback_rate,
        "label_counts": dict(label_counts),
        "fallback_reasons": dict(fallback_reasons),
        "confidence_buckets": dict(confidence_buckets),
        "reasoning_floored_count": floored,
        "moved_from_fallback_count": len(moved_from_fallback)
    }
    
    return results, decisions


if __name__ == '__main__':
    run_test()
