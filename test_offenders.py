#!/usr/bin/env python3
"""
Token Guardian <0.60 Top Offenders Report
Analyzes why queries score below 0.60
"""
import sys
from pathlib import Path
from collections import defaultdict, Counter
import re

sys.path.insert(0, str(Path(__file__).parent))

from src.core.classifier import Classifier
from src.core.pipeline import create_pipeline


# Same test set (223 queries)
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


def run_offenders_report():
    """Generate the <0.60 Top Offenders report"""
    print("=" * 100)
    print("TOKEN GUARDIAN <0.60 TOP OFFENDERS REPORT")
    print("=" * 100)
    print()
    
    classifier = Classifier()
    pipeline = create_pipeline(shadow_mode=True)
    
    # Track metrics
    offenders = []
    by_label = defaultdict(list)
    zero_keyword_matches = []
    vague_hits = []
    all_words = []
    
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
        'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 's', 't', 'just', 'don', 'now', 'i', 'me', 'my',
        'we', 'our', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it',
        'its', 'they', 'them', 'their', 'what', 'this', 'that', 'these',
        'those', 'am', 'about', 'and', 'or', 'but', 'if', 'because', 'until',
        'while', 'although', 'though', 'after', 'before', 'when', 'whenever',
        'where', 'wherever', 'whether', 'which', 'while', 'who', 'whom',
        'whose', 'why', 'give', 'get', 'make', 'made', 'take', 'took',
    }
    
    for query in TEST_QUERIES:
        result = classifier.classify(query)
        decision = pipeline.process(query)
        
        # Extract words for frequency analysis
        words = re.findall(r'\b\w+\b', query.lower())
        content_words = [w for w in words if w not in stopwords and len(w) > 2]
        all_words.extend(content_words)
        
        if result.confidence < 0.60:
            # Analyze why score is low
            analysis = {
                "query": query,
                "label": result.label,
                "confidence": result.confidence,
                "keywords": result.matched_keywords,
                "is_vague": result.is_vague,
                "reasoning": result.reasoning,
            }
            
            # Diagnose
            if len(result.matched_keywords) == 0:
                analysis["diagnosis"] = "ZERO_MATCHES"
                zero_keyword_matches.append(query)
            elif result.is_vague:
                analysis["diagnosis"] = "VAGUE_HIT"
                vague_hits.append(query)
            elif result.confidence < 0.30:
                analysis["diagnosis"] = "VERY_LOW"
            elif result.label == 'general':
                analysis["diagnosis"] = "LABEL_IS_GENERAL"
            else:
                analysis["diagnosis"] = "PARTIAL_MATCH"
            
            offenders.append(analysis)
            by_label[result.label].append(query)
    
    # Report
    print(f"Total queries: {len(TEST_QUERIES)}")
    print(f"<0.60 offenders: {len(offenders)} ({len(offenders)/len(TEST_QUERIES)*100:.1f}%)")
    print()
    
    print("-" * 100)
    print("BREAKDOWN BY LABEL")
    print("-" * 100)
    for label, queries in sorted(by_label.items(), key=lambda x: -len(x[1])):
        print(f"  {label:18}: {len(queries):3} ({len(queries)/len(offenders)*100:.1f}% of offenders)")
    print()
    
    print("-" * 100)
    print("DIAGNOSIS BREAKDOWN")
    print("-" * 100)
    diagnoses = defaultdict(int)
    for o in offenders:
        diagnoses[o["diagnosis"]] += 1
    for diag, count in sorted(diagnoses.items(), key=lambda x: -x[1]):
        print(f"  {diag:20}: {count}")
    print()
    
    print("-" * 100)
    print("ZERO MATCH EXAMPLES (first 10)")
    print("-" * 100)
    for q in zero_keyword_matches[:10]:
        print(f"  {q}")
    print()
    
    print("-" * 100)
    print("TOP 20 WORDS IN <0.60 QUERIES")
    print("-" * 100)
    word_freq = Counter(all_words)
    for word, count in word_freq.most_common(20):
        print(f"  {word:20}: {count}")
    print()
    
    print("-" * 100)
    print("DETAILED OFFENDERS (first 30)")
    print("-" * 100)
    for i, o in enumerate(offenders[:30]):
        print(f"\n{i+1}. Query: {o['query'][:60]}...")
        print(f"   Label: {o['label']} | Conf: {o['confidence']:.2f}")
        print(f"   Keywords: {o['keywords'] if o['keywords'] else 'NONE'}")
        print(f"   Diagnosis: {o['diagnosis']}")
        print(f"   Reasoning: {o['reasoning']}")
    
    return {
        "total": len(TEST_QUERIES),
        "offenders": len(offenders),
        "by_label": {k: len(v) for k, v in by_label.items()},
        "zero_matches": len(zero_keyword_matches),
        "vague_hits": len(vague_hits),
        "word_freq": word_freq.most_common(20),
    }


if __name__ == '__main__':
    run_offenders_report()
