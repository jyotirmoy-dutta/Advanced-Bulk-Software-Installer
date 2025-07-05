#!/usr/bin/env python3
"""
Advanced Search and Discovery System
Provides fuzzy matching, package recommendations, and repository indexing
"""

import json
import sqlite3
import logging
import time
import threading
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
from datetime import datetime, timedelta
from enum import Enum
import re
import hashlib
from collections import defaultdict, Counter
import asyncio
import aiohttp
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle

class SearchIndex(Enum):
    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"

class PackageCategory(Enum):
    DEVELOPMENT = "development"
    PRODUCTIVITY = "productivity"
    GAMING = "gaming"
    SECURITY = "security"
    MULTIMEDIA = "multimedia"
    UTILITIES = "utilities"
    NETWORKING = "networking"
    SYSTEM = "system"

@dataclass
class PackageMetadata:
    """Package metadata for search and discovery."""
    name: str
    manager: str
    version: str
    description: str
    category: PackageCategory
    tags: List[str]
    dependencies: List[str]
    size: int
    popularity: float
    rating: float
    last_updated: datetime
    maintainer: str
    repository: str
    license: str
    homepage: str
    documentation: str
    keywords: List[str]
    alternatives: List[str]

@dataclass
class SearchResult:
    """Search result with relevance scoring."""
    package: PackageMetadata
    relevance_score: float
    match_type: str
    matched_fields: List[str]
    snippet: str

@dataclass
class Recommendation:
    """Package recommendation."""
    package: PackageMetadata
    reason: str
    confidence: float
    based_on: List[str]

class RepositoryIndexer:
    """Indexes package repositories for fast search."""
    
    def __init__(self, db_path: str = "package_index.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.index_lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # Index data
        self.package_index: Dict[str, PackageMetadata] = {}
        self.name_index: Dict[str, Set[str]] = defaultdict(set)
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.category_index: Dict[PackageCategory, Set[str]] = defaultdict(set)
        self.keyword_index: Dict[str, Set[str]] = defaultdict(set)
        
        # TF-IDF vectorizer for semantic search
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = None
        self.package_names = []
        
        # Load existing index
        self._load_index()
    
    def _init_database(self):
        """Initialize package index database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS package_metadata (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    manager TEXT,
                    version TEXT,
                    description TEXT,
                    category TEXT,
                    tags TEXT,
                    dependencies TEXT,
                    size INTEGER,
                    popularity REAL,
                    rating REAL,
                    last_updated TEXT,
                    maintainer TEXT,
                    repository TEXT,
                    license TEXT,
                    homepage TEXT,
                    documentation TEXT,
                    keywords TEXT,
                    alternatives TEXT,
                    indexed_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_log (
                    id TEXT PRIMARY KEY,
                    query TEXT,
                    results_count INTEGER,
                    execution_time REAL,
                    timestamp TEXT,
                    user_agent TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS package_views (
                    id TEXT PRIMARY KEY,
                    package_id TEXT,
                    timestamp TEXT,
                    source TEXT
                )
            ''')
            
            conn.commit()
    
    def _load_index(self):
        """Load package index from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM package_metadata')
            for row in cursor.fetchall():
                package = PackageMetadata(
                    name=row[1],
                    manager=row[2],
                    version=row[3],
                    description=row[4],
                    category=PackageCategory(row[5]),
                    tags=json.loads(row[6]),
                    dependencies=json.loads(row[7]),
                    size=row[8],
                    popularity=row[9],
                    rating=row[10],
                    last_updated=datetime.fromisoformat(row[11]),
                    maintainer=row[12],
                    repository=row[13],
                    license=row[14],
                    homepage=row[15],
                    documentation=row[16],
                    keywords=json.loads(row[17]),
                    alternatives=json.loads(row[18])
                )
                
                package_id = row[0]
                self.package_index[package_id] = package
                
                # Update indexes
                self._update_indexes(package_id, package)
        
        # Build TF-IDF matrix
        self._build_tfidf_matrix()
    
    def _update_indexes(self, package_id: str, package: PackageMetadata):
        """Update search indexes for a package."""
        # Name index
        self.name_index[package.name.lower()].add(package_id)
        
        # Tag index
        for tag in package.tags:
            self.tag_index[tag.lower()].add(package_id)
        
        # Category index
        self.category_index[package.category].add(package_id)
        
        # Keyword index
        for keyword in package.keywords:
            self.keyword_index[keyword.lower()].add(package_id)
    
    def _build_tfidf_matrix(self):
        """Build TF-IDF matrix for semantic search."""
        if not self.package_index:
            return
        
        # Prepare documents for vectorization
        documents = []
        self.package_names = []
        
        for package_id, package in self.package_index.items():
            doc = f"{package.name} {package.description} {' '.join(package.tags)} {' '.join(package.keywords)}"
            documents.append(doc)
            self.package_names.append(package_id)
        
        # Build TF-IDF matrix
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
    
    def index_package(self, package: PackageMetadata) -> str:
        """Index a package for search."""
        package_id = str(uuid.uuid4())
        
        with self.index_lock:
            # Save to database
            self._save_package(package_id, package)
            
            # Update memory index
            self.package_index[package_id] = package
            self._update_indexes(package_id, package)
            
            # Rebuild TF-IDF matrix
            self._build_tfidf_matrix()
        
        return package_id
    
    def _save_package(self, package_id: str, package: PackageMetadata):
        """Save package to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO package_metadata 
                (id, name, manager, version, description, category, tags, dependencies,
                 size, popularity, rating, last_updated, maintainer, repository, license,
                 homepage, documentation, keywords, alternatives, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                package_id, package.name, package.manager, package.version,
                package.description, package.category.value, json.dumps(package.tags),
                json.dumps(package.dependencies), package.size, package.popularity,
                package.rating, package.last_updated.isoformat(), package.maintainer,
                package.repository, package.license, package.homepage,
                package.documentation, json.dumps(package.keywords),
                json.dumps(package.alternatives), datetime.now().isoformat()
            ))
            conn.commit()
    
    def search_packages(self, query: str, limit: int = 20, 
                       filters: Dict = None) -> List[SearchResult]:
        """Search packages using multiple strategies."""
        start_time = time.time()
        
        with self.index_lock:
            # Apply filters
            candidate_packages = self._apply_filters(filters)
            
            # Perform search
            results = []
            
            # 1. Exact name match
            exact_matches = self._exact_name_search(query, candidate_packages)
            results.extend(exact_matches)
            
            # 2. Fuzzy name search
            fuzzy_matches = self._fuzzy_name_search(query, candidate_packages, limit=limit//2)
            results.extend(fuzzy_matches)
            
            # 3. Tag and keyword search
            tag_matches = self._tag_keyword_search(query, candidate_packages, limit=limit//4)
            results.extend(tag_matches)
            
            # 4. Semantic search
            semantic_matches = self._semantic_search(query, candidate_packages, limit=limit//4)
            results.extend(semantic_matches)
            
            # Remove duplicates and sort by relevance
            unique_results = self._deduplicate_results(results)
            sorted_results = sorted(unique_results, key=lambda r: r.relevance_score, reverse=True)
            
            # Log search
            execution_time = time.time() - start_time
            self._log_search(query, len(sorted_results), execution_time)
            
            return sorted_results[:limit]
    
    def _apply_filters(self, filters: Dict) -> Set[str]:
        """Apply search filters."""
        if not filters:
            return set(self.package_index.keys())
        
        filtered_packages = set(self.package_index.keys())
        
        if 'manager' in filters:
            manager_filter = set()
            for package_id, package in self.package_index.items():
                if package.manager in filters['manager']:
                    manager_filter.add(package_id)
            filtered_packages &= manager_filter
        
        if 'category' in filters:
            category_filter = set()
            for category in filters['category']:
                category_filter |= self.category_index.get(PackageCategory(category), set())
            filtered_packages &= category_filter
        
        if 'min_rating' in filters:
            rating_filter = set()
            for package_id, package in self.package_index.items():
                if package.rating >= filters['min_rating']:
                    rating_filter.add(package_id)
            filtered_packages &= rating_filter
        
        return filtered_packages
    
    def _exact_name_search(self, query: str, candidate_packages: Set[str]) -> List[SearchResult]:
        """Exact name search."""
        results = []
        query_lower = query.lower()
        
        for package_id in candidate_packages:
            package = self.package_index[package_id]
            if query_lower == package.name.lower():
                results.append(SearchResult(
                    package=package,
                    relevance_score=1.0,
                    match_type="exact_name",
                    matched_fields=["name"],
                    snippet=package.description[:200]
                ))
        
        return results
    
    def _fuzzy_name_search(self, query: str, candidate_packages: Set[str], 
                          limit: int) -> List[SearchResult]:
        """Fuzzy name search."""
        results = []
        query_lower = query.lower()
        
        for package_id in candidate_packages:
            package = self.package_index[package_id]
            ratio = fuzz.ratio(query_lower, package.name.lower())
            
            if ratio > 70:  # Threshold for fuzzy matching
                results.append(SearchResult(
                    package=package,
                    relevance_score=ratio / 100.0,
                    match_type="fuzzy_name",
                    matched_fields=["name"],
                    snippet=package.description[:200]
                ))
        
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)[:limit]
    
    def _tag_keyword_search(self, query: str, candidate_packages: Set[str], 
                           limit: int) -> List[SearchResult]:
        """Search by tags and keywords."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for package_id in candidate_packages:
            package = self.package_index[package_id]
            matched_fields = []
            score = 0.0
            
            # Check tags
            for tag in package.tags:
                if query_lower in tag.lower() or any(word in tag.lower() for word in query_words):
                    matched_fields.append("tags")
                    score += 0.3
            
            # Check keywords
            for keyword in package.keywords:
                if query_lower in keyword.lower() or any(word in keyword.lower() for word in query_words):
                    matched_fields.append("keywords")
                    score += 0.2
            
            if score > 0:
                results.append(SearchResult(
                    package=package,
                    relevance_score=min(score, 1.0),
                    match_type="tag_keyword",
                    matched_fields=list(set(matched_fields)),
                    snippet=package.description[:200]
                ))
        
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)[:limit]
    
    def _semantic_search(self, query: str, candidate_packages: Set[str], 
                        limit: int) -> List[SearchResult]:
        """Semantic search using TF-IDF."""
        if self.tfidf_matrix is None:
            return []
        
        results = []
        
        # Transform query
        query_vector = self.vectorizer.transform([query])
        
        # Calculate similarities
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # Get top matches
        top_indices = similarities.argsort()[-limit:][::-1]
        
        for idx in top_indices:
            if similarities[idx] > 0.1:  # Threshold for semantic matching
                package_id = self.package_names[idx]
                if package_id in candidate_packages:
                    package = self.package_index[package_id]
                    results.append(SearchResult(
                        package=package,
                        relevance_score=float(similarities[idx]),
                        match_type="semantic",
                        matched_fields=["description", "tags", "keywords"],
                        snippet=package.description[:200]
                    ))
        
        return results
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results and merge scores."""
        package_scores = defaultdict(list)
        
        for result in results:
            package_scores[result.package.name].append(result)
        
        unique_results = []
        for package_name, result_list in package_scores.items():
            if len(result_list) == 1:
                unique_results.append(result_list[0])
            else:
                # Merge multiple results for the same package
                best_result = max(result_list, key=lambda r: r.relevance_score)
                best_result.relevance_score = min(1.0, sum(r.relevance_score for r in result_list))
                best_result.matched_fields = list(set(
                    field for r in result_list for field in r.matched_fields
                ))
                unique_results.append(best_result)
        
        return unique_results
    
    def _log_search(self, query: str, results_count: int, execution_time: float):
        """Log search query for analytics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO search_log 
                (id, query, results_count, execution_time, timestamp, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), query, results_count, execution_time,
                datetime.now().isoformat(), "bulk_installer"
            ))
            conn.commit()
    
    def log_package_view(self, package_id: str, source: str = "search"):
        """Log package view for analytics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO package_views 
                (id, package_id, timestamp, source)
                VALUES (?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), package_id, datetime.now().isoformat(), source
            ))
            conn.commit()

class PackageRecommender:
    """Recommends packages based on various algorithms."""
    
    def __init__(self, indexer: RepositoryIndexer):
        self.indexer = indexer
        self.logger = logging.getLogger(__name__)
        
        # Recommendation algorithms
        self.algorithms = {
            'popular': self._popularity_based,
            'similar': self._similarity_based,
            'collaborative': self._collaborative_filtering,
            'content': self._content_based,
            'hybrid': self._hybrid_recommendation
        }
    
    def get_recommendations(self, context: Dict, algorithm: str = 'hybrid', 
                          limit: int = 10) -> List[Recommendation]:
        """Get package recommendations."""
        if algorithm not in self.algorithms:
            algorithm = 'hybrid'
        
        recommendations = self.algorithms[algorithm](context, limit)
        
        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        
        return recommendations[:limit]
    
    def _popularity_based(self, context: Dict, limit: int) -> List[Recommendation]:
        """Popularity-based recommendations."""
        recommendations = []
        
        # Get most popular packages
        popular_packages = sorted(
            self.indexer.package_index.values(),
            key=lambda p: p.popularity,
            reverse=True
        )
        
        for package in popular_packages[:limit]:
            recommendations.append(Recommendation(
                package=package,
                reason="High popularity",
                confidence=min(package.popularity / 100.0, 1.0),
                based_on=["popularity"]
            ))
        
        return recommendations
    
    def _similarity_based(self, context: Dict, limit: int) -> List[Recommendation]:
        """Similarity-based recommendations."""
        recommendations = []
        
        if 'current_packages' not in context:
            return recommendations
        
        current_packages = context['current_packages']
        package_scores = defaultdict(float)
        
        for current_pkg in current_packages:
            current_metadata = self._get_package_metadata(current_pkg)
            if not current_metadata:
                continue
            
            # Find similar packages
            for package in self.indexer.package_index.values():
                if package.name == current_metadata.name:
                    continue
                
                similarity = self._calculate_similarity(current_metadata, package)
                package_scores[package.name] += similarity
        
        # Get top similar packages
        sorted_packages = sorted(
            package_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for package_name, score in sorted_packages[:limit]:
            package = self._get_package_by_name(package_name)
            if package:
                recommendations.append(Recommendation(
                    package=package,
                    reason="Similar to installed packages",
                    confidence=min(score, 1.0),
                    based_on=["similarity"]
                ))
        
        return recommendations
    
    def _collaborative_filtering(self, context: Dict, limit: int) -> List[Recommendation]:
        """Collaborative filtering recommendations."""
        # This would typically use user behavior data
        # For now, return empty list
        return []
    
    def _content_based(self, context: Dict, limit: int) -> List[Recommendation]:
        """Content-based recommendations."""
        recommendations = []
        
        if 'interests' not in context:
            return recommendations
        
        interests = context['interests']
        package_scores = defaultdict(float)
        
        for package in self.indexer.package_index.values():
            score = 0.0
            
            # Match interests with package tags and keywords
            for interest in interests:
                if interest.lower() in package.name.lower():
                    score += 0.3
                
                for tag in package.tags:
                    if interest.lower() in tag.lower():
                        score += 0.2
                
                for keyword in package.keywords:
                    if interest.lower() in keyword.lower():
                        score += 0.1
            
            if score > 0:
                package_scores[package.name] = score
        
        # Get top matches
        sorted_packages = sorted(
            package_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for package_name, score in sorted_packages[:limit]:
            package = self._get_package_by_name(package_name)
            if package:
                recommendations.append(Recommendation(
                    package=package,
                    reason="Matches your interests",
                    confidence=min(score, 1.0),
                    based_on=["content"]
                ))
        
        return recommendations
    
    def _hybrid_recommendation(self, context: Dict, limit: int) -> List[Recommendation]:
        """Hybrid recommendation combining multiple algorithms."""
        all_recommendations = []
        
        # Get recommendations from different algorithms
        popular_recs = self._popularity_based(context, limit)
        similar_recs = self._similarity_based(context, limit)
        content_recs = self._content_based(context, limit)
        
        all_recommendations.extend(popular_recs)
        all_recommendations.extend(similar_recs)
        all_recommendations.extend(content_recs)
        
        # Aggregate scores
        package_scores = defaultdict(list)
        for rec in all_recommendations:
            package_scores[rec.package.name].append(rec)
        
        # Combine recommendations
        final_recommendations = []
        for package_name, rec_list in package_scores.items():
            if len(rec_list) == 1:
                final_recommendations.append(rec_list[0])
            else:
                # Combine multiple recommendations
                combined_confidence = sum(r.confidence for r in rec_list) / len(rec_list)
                combined_reasons = list(set(r.reason for r in rec_list))
                combined_based_on = list(set(
                    source for r in rec_list for source in r.based_on
                ))
                
                final_recommendations.append(Recommendation(
                    package=rec_list[0].package,
                    reason="; ".join(combined_reasons),
                    confidence=min(combined_confidence, 1.0),
                    based_on=combined_based_on
                ))
        
        return sorted(final_recommendations, key=lambda r: r.confidence, reverse=True)[:limit]
    
    def _calculate_similarity(self, pkg1: PackageMetadata, pkg2: PackageMetadata) -> float:
        """Calculate similarity between two packages."""
        similarity = 0.0
        
        # Category similarity
        if pkg1.category == pkg2.category:
            similarity += 0.3
        
        # Tag similarity
        common_tags = set(pkg1.tags) & set(pkg2.tags)
        similarity += len(common_tags) * 0.1
        
        # Keyword similarity
        common_keywords = set(pkg1.keywords) & set(pkg2.keywords)
        similarity += len(common_keywords) * 0.05
        
        # Description similarity (simplified)
        if pkg1.description and pkg2.description:
            desc_similarity = fuzz.ratio(pkg1.description.lower(), pkg2.description.lower())
            similarity += desc_similarity / 100.0 * 0.2
        
        return min(similarity, 1.0)
    
    def _get_package_metadata(self, package_name: str) -> Optional[PackageMetadata]:
        """Get package metadata by name."""
        for package in self.indexer.package_index.values():
            if package.name == package_name:
                return package
        return None
    
    def _get_package_by_name(self, package_name: str) -> Optional[PackageMetadata]:
        """Get package by name."""
        return self._get_package_metadata(package_name)

class PackageDiscovery:
    """Main package discovery and search system."""
    
    def __init__(self, index_mode: SearchIndex = SearchIndex.HYBRID):
        self.index_mode = index_mode
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.indexer = RepositoryIndexer()
        self.recommender = PackageRecommender(self.indexer)
        
        # Search statistics
        self.search_stats = {
            'total_searches': 0,
            'popular_queries': Counter(),
            'search_times': [],
            'result_counts': []
        }
    
    def search(self, query: str, limit: int = 20, filters: Dict = None) -> List[SearchResult]:
        """Search for packages."""
        self.search_stats['total_searches'] += 1
        self.search_stats['popular_queries'][query] += 1
        
        start_time = time.time()
        results = self.indexer.search_packages(query, limit, filters)
        search_time = time.time() - start_time
        
        # Update statistics
        self.search_stats['search_times'].append(search_time)
        self.search_stats['result_counts'].append(len(results))
        
        return results
    
    def get_recommendations(self, context: Dict, algorithm: str = 'hybrid', 
                          limit: int = 10) -> List[Recommendation]:
        """Get package recommendations."""
        return self.recommender.get_recommendations(context, algorithm, limit)
    
    def discover_packages(self, category: PackageCategory = None, 
                         limit: int = 20) -> List[PackageMetadata]:
        """Discover packages by category."""
        if category:
            package_ids = self.indexer.category_index.get(category, set())
        else:
            package_ids = set(self.indexer.package_index.keys())
        
        packages = []
        for package_id in list(package_ids)[:limit]:
            packages.append(self.indexer.package_index[package_id])
        
        # Sort by popularity
        packages.sort(key=lambda p: p.popularity, reverse=True)
        
        return packages
    
    def get_trending_packages(self, days: int = 7, limit: int = 10) -> List[PackageMetadata]:
        """Get trending packages based on recent activity."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        trending_packages = []
        for package in self.indexer.package_index.values():
            if package.last_updated >= cutoff_date:
                trending_packages.append(package)
        
        # Sort by popularity and recency
        trending_packages.sort(
            key=lambda p: (p.popularity, p.last_updated),
            reverse=True
        )
        
        return trending_packages[:limit]
    
    def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get search suggestions for autocomplete."""
        suggestions = []
        partial_lower = partial_query.lower()
        
        # Name suggestions
        for package in self.indexer.package_index.values():
            if package.name.lower().startswith(partial_lower):
                suggestions.append(package.name)
                if len(suggestions) >= limit:
                    break
        
        # Tag suggestions
        if len(suggestions) < limit:
            for tag in self.indexer.tag_index.keys():
                if tag.startswith(partial_lower):
                    suggestions.append(tag)
                    if len(suggestions) >= limit:
                        break
        
        return suggestions[:limit]
    
    def get_search_statistics(self) -> Dict:
        """Get search statistics."""
        if not self.search_stats['search_times']:
            return {
                'total_searches': 0,
                'avg_search_time': 0,
                'avg_results': 0,
                'popular_queries': []
            }
        
        return {
            'total_searches': self.search_stats['total_searches'],
            'avg_search_time': np.mean(self.search_stats['search_times']),
            'avg_results': np.mean(self.search_stats['result_counts']),
            'popular_queries': self.search_stats['popular_queries'].most_common(10)
        }
    
    def log_package_view(self, package_name: str, source: str = "search"):
        """Log package view for analytics."""
        for package_id, package in self.indexer.package_index.items():
            if package.name == package_name:
                self.indexer.log_package_view(package_id, source)
                break

# Global package discovery instance
package_discovery = PackageDiscovery() 