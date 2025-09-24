"""
Advanced Memory Management System for AI Agent
Implements hierarchical memory architecture with consolidation protocols
"""

import json
import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from collections import deque, defaultdict
import pickle
from flask import current_app, session, g

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class MemoryEntry:
    """Base class for memory entries"""
    timestamp: datetime
    content: Dict[str, Any]
    importance: float  # 0.0-1.0 importance score
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def access(self):
        """Mark this memory as accessed"""
        self.access_count += 1
        self.last_accessed = datetime.now()

@dataclass
class ConversationExchange:
    """Represents a single conversation exchange"""
    user_message: str
    agent_response: str
    intent: str
    entities: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: datetime
    confidence: float
    task_context: Optional[str] = None

@dataclass
class UserProfile:
    """Persistent user profile with learned characteristics"""
    user_id: str
    expertise_level: str = "intermediate"  # beginner, intermediate, expert
    communication_style: str = "professional"  # casual, professional, technical
    preferred_detail_level: str = "medium"  # low, medium, high
    common_tasks: List[str] = field(default_factory=list)
    domain_expertise: Dict[str, float] = field(default_factory=dict)  # domain -> expertise score
    workflow_patterns: Dict[str, int] = field(default_factory=dict)  # pattern -> frequency
    template_preferences: Dict[str, str] = field(default_factory=dict)
    response_preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0
    successful_completions: int = 0

class ShortTermMemory:
    """Manages immediate conversation context and active parameters"""
    
    def __init__(self, max_exchanges: int = 20):
        self.max_exchanges = max_exchanges
        self.conversation_history: deque = deque(maxlen=max_exchanges)
        self.current_task_context: Dict[str, Any] = {}
        self.active_parameters: Dict[str, Any] = {}
        self.immediate_preferences: Dict[str, Any] = {}
        self.workflow_state: Dict[str, Any] = {}
        self.corrections: List[Dict[str, Any]] = []
        
    def add_exchange(self, exchange: ConversationExchange):
        """Add a conversation exchange to short-term memory"""
        self.conversation_history.append(exchange)
        
        # Update active parameters based on exchange
        if exchange.entities:
            self.active_parameters.update(exchange.entities)
            
        # Track task context
        if exchange.task_context:
            self.current_task_context['current_task'] = exchange.task_context
            self.current_task_context['last_updated'] = exchange.timestamp
    
    def get_recent_context(self, n: int = 5) -> List[ConversationExchange]:
        """Get the most recent n exchanges"""
        return list(self.conversation_history)[-n:]
    
    def update_task_context(self, context: Dict[str, Any]):
        """Update current task context"""
        self.current_task_context.update(context)
        self.current_task_context['last_updated'] = datetime.now()
    
    def add_correction(self, correction: Dict[str, Any]):
        """Add user correction to immediate memory"""
        correction['timestamp'] = datetime.now()
        self.corrections.append(correction)
        
        # Keep only recent corrections
        if len(self.corrections) > 10:
            self.corrections = self.corrections[-10:]
    
    def get_active_context(self) -> Dict[str, Any]:
        """Get comprehensive active context"""
        return {
            'recent_exchanges': len(self.conversation_history),
            'current_task': self.current_task_context.get('current_task'),
            'active_parameters': self.active_parameters,
            'workflow_state': self.workflow_state,
            'recent_corrections': self.corrections[-3:] if self.corrections else []
        }

class MidTermMemory:
    """Manages session-based knowledge and project-specific information"""
    
    def __init__(self):
        self.session_id: Optional[str] = None
        self.project_knowledge: Dict[str, Any] = {}
        self.workflow_patterns: Dict[str, List[str]] = defaultdict(list)
        self.template_customizations: Dict[str, Dict[str, Any]] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.task_dependencies: Dict[str, List[str]] = defaultdict(list)
        self.project_relationships: Dict[str, List[str]] = defaultdict(list)
        self.session_insights: List[MemoryEntry] = []
        self.decision_history: List[Dict[str, Any]] = []
        self.session_start: datetime = datetime.now()
        
    def start_session(self, session_id: str):
        """Initialize a new session"""
        self.session_id = session_id
        self.session_start = datetime.now()
        logger.info(f"Started new mid-term memory session: {session_id}")
    
    def add_project_knowledge(self, project_id: str, knowledge: Dict[str, Any]):
        """Add project-specific knowledge"""
        if project_id not in self.project_knowledge:
            self.project_knowledge[project_id] = {}
        
        self.project_knowledge[project_id].update(knowledge)
        self.project_knowledge[project_id]['last_updated'] = datetime.now()
    
    def track_workflow_pattern(self, pattern_name: str, steps: List[str]):
        """Track workflow patterns within session"""
        self.workflow_patterns[pattern_name].extend(steps)
    
    def add_template_customization(self, template_type: str, customizations: Dict[str, Any]):
        """Store template customizations"""
        self.template_customizations[template_type] = customizations
        self.template_customizations[template_type]['timestamp'] = datetime.now()
    
    def add_task_dependency(self, task: str, dependencies: List[str]):
        """Track task dependencies"""
        self.task_dependencies[task].extend(dependencies)
    
    def add_project_relationship(self, project: str, related_projects: List[str]):
        """Track project relationships"""
        self.project_relationships[project].extend(related_projects)
    
    def add_insight(self, insight: MemoryEntry):
        """Add session insight"""
        self.session_insights.append(insight)
        
        # Keep insights sorted by importance
        self.session_insights.sort(key=lambda x: x.importance, reverse=True)
        
        # Limit number of insights
        if len(self.session_insights) > 50:
            self.session_insights = self.session_insights[:50]
    
    def record_decision(self, decision: Dict[str, Any]):
        """Record important decisions made in session"""
        decision['timestamp'] = datetime.now()
        decision['session_id'] = self.session_id
        self.decision_history.append(decision)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary"""
        return {
            'session_id': self.session_id,
            'duration': datetime.now() - self.session_start,
            'projects_worked_on': list(self.project_knowledge.keys()),
            'workflow_patterns': dict(self.workflow_patterns),
            'template_customizations': list(self.template_customizations.keys()),
            'key_insights': [asdict(insight) for insight in self.session_insights[:5]],
            'decisions_made': len(self.decision_history),
            'task_dependencies': dict(self.task_dependencies)
        }

class LongTermMemory:
    """Manages persistent learning and cross-session knowledge"""
    
    def __init__(self, storage_path: str = "instance/memory"):
        self.storage_path = storage_path
        self.user_profiles: Dict[str, UserProfile] = {}
        self.domain_knowledge: Dict[str, MemoryEntry] = {}
        self.historical_patterns: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.cross_project_insights: List[MemoryEntry] = []
        self.optimization_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.global_statistics: Dict[str, Any] = {}
        
        # Ensure storage directory exists
        os.makedirs(storage_path, exist_ok=True)
        
        # Load existing data
        self._load_persistent_data()
    
    def _get_user_profile_path(self, user_id: str) -> str:
        """Get file path for user profile"""
        safe_user_id = hashlib.md5(user_id.encode()).hexdigest()
        return os.path.join(self.storage_path, f"profile_{safe_user_id}.pkl")
    
    def _get_domain_knowledge_path(self) -> str:
        """Get file path for domain knowledge"""
        return os.path.join(self.storage_path, "domain_knowledge.pkl")
    
    def _get_patterns_path(self) -> str:
        """Get file path for historical patterns"""
        return os.path.join(self.storage_path, "historical_patterns.pkl")
    
    def _load_persistent_data(self):
        """Load persistent data from storage"""
        try:
            # Load domain knowledge
            domain_path = self._get_domain_knowledge_path()
            if os.path.exists(domain_path):
                with open(domain_path, 'rb') as f:
                    self.domain_knowledge = pickle.load(f)
            
            # Load historical patterns
            patterns_path = self._get_patterns_path()
            if os.path.exists(patterns_path):
                with open(patterns_path, 'rb') as f:
                    data = pickle.load(f)
                    self.historical_patterns = data.get('patterns', defaultdict(dict))
                    self.cross_project_insights = data.get('insights', [])
                    self.optimization_patterns = data.get('optimizations', defaultdict(list))
                    self.global_statistics = data.get('statistics', {})
                    
        except Exception as e:
            logger.error(f"Error loading persistent memory data: {e}")
    
    def _save_persistent_data(self):
        """Save persistent data to storage"""
        try:
            # Save domain knowledge
            domain_path = self._get_domain_knowledge_path()
            with open(domain_path, 'wb') as f:
                pickle.dump(self.domain_knowledge, f)
            
            # Save historical patterns and insights
            patterns_path = self._get_patterns_path()
            data = {
                'patterns': dict(self.historical_patterns),
                'insights': self.cross_project_insights,
                'optimizations': dict(self.optimization_patterns),
                'statistics': self.global_statistics
            }
            with open(patterns_path, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"Error saving persistent memory data: {e}")
    
    def get_user_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile"""
        if user_id not in self.user_profiles:
            # Try to load from storage
            profile_path = self._get_user_profile_path(user_id)
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'rb') as f:
                        self.user_profiles[user_id] = pickle.load(f)
                except Exception as e:
                    logger.error(f"Error loading user profile: {e}")
                    self.user_profiles[user_id] = UserProfile(user_id=user_id)
            else:
                self.user_profiles[user_id] = UserProfile(user_id=user_id)
        
        return self.user_profiles[user_id]
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """Update user profile with new information"""
        profile = self.get_user_profile(user_id)
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
        profile.total_interactions += 1
        
        # Save to storage
        self._save_user_profile(user_id, profile)
    
    def _save_user_profile(self, user_id: str, profile: UserProfile):
        """Save user profile to storage"""
        try:
            profile_path = self._get_user_profile_path(user_id)
            with open(profile_path, 'wb') as f:
                pickle.dump(profile, f)
        except Exception as e:
            logger.error(f"Error saving user profile: {e}")
    
    def add_domain_knowledge(self, domain: str, knowledge: Dict[str, Any], importance: float = 0.5):
        """Add domain-specific knowledge"""
        entry = MemoryEntry(
            timestamp=datetime.now(),
            content=knowledge,
            importance=importance,
            tags=[domain, 'domain_knowledge']
        )
        
        key = f"{domain}_{datetime.now().isoformat()}"
        self.domain_knowledge[key] = entry
        
        # Cleanup old entries if too many
        if len(self.domain_knowledge) > 1000:
            # Keep only the most important and recent entries
            sorted_entries = sorted(
                self.domain_knowledge.items(),
                key=lambda x: (x[1].importance, x[1].timestamp),
                reverse=True
            )
            self.domain_knowledge = dict(sorted_entries[:800])
        
        self._save_persistent_data()
    
    def add_historical_pattern(self, pattern_type: str, pattern_data: Dict[str, Any]):
        """Add historical pattern"""
        if pattern_type not in self.historical_patterns:
            self.historical_patterns[pattern_type] = {
                'occurrences': 0,
                'data': [],
                'first_seen': datetime.now(),
                'last_seen': datetime.now()
            }
        
        self.historical_patterns[pattern_type]['occurrences'] += 1
        self.historical_patterns[pattern_type]['data'].append({
            'timestamp': datetime.now(),
            'data': pattern_data
        })
        self.historical_patterns[pattern_type]['last_seen'] = datetime.now()
        
        # Keep only recent pattern data
        if len(self.historical_patterns[pattern_type]['data']) > 100:
            self.historical_patterns[pattern_type]['data'] = \
                self.historical_patterns[pattern_type]['data'][-50:]
        
        self._save_persistent_data()
    
    def add_cross_project_insight(self, insight: MemoryEntry):
        """Add cross-project insight"""
        self.cross_project_insights.append(insight)
        
        # Sort by importance and keep top insights
        self.cross_project_insights.sort(key=lambda x: x.importance, reverse=True)
        if len(self.cross_project_insights) > 200:
            self.cross_project_insights = self.cross_project_insights[:150]
        
        self._save_persistent_data()
    
    def add_optimization_pattern(self, optimization_type: str, pattern: Dict[str, Any]):
        """Add optimization pattern"""
        pattern['timestamp'] = datetime.now()
        self.optimization_patterns[optimization_type].append(pattern)
        
        # Keep recent patterns
        if len(self.optimization_patterns[optimization_type]) > 50:
            self.optimization_patterns[optimization_type] = \
                self.optimization_patterns[optimization_type][-30:]
        
        self._save_persistent_data()
    
    def get_relevant_knowledge(self, query_tags: List[str], limit: int = 10) -> List[MemoryEntry]:
        """Get relevant knowledge based on tags"""
        relevant_entries = []
        
        for entry in self.domain_knowledge.values():
            if any(tag in entry.tags for tag in query_tags):
                entry.access()
                relevant_entries.append(entry)
        
        # Sort by relevance (importance + recency + access count)
        relevant_entries.sort(
            key=lambda x: (
                x.importance * 0.5 +
                (datetime.now() - x.timestamp).days * -0.01 +
                x.access_count * 0.1
            ),
            reverse=True
        )
        
        return relevant_entries[:limit]
    
    def update_global_statistics(self, stats: Dict[str, Any]):
        """Update global statistics"""
        self.global_statistics.update(stats)
        self.global_statistics['last_updated'] = datetime.now()
        self._save_persistent_data()

class MemoryConsolidationProtocol:
    """Handles memory consolidation between different memory levels"""
    
    def __init__(self, short_term: ShortTermMemory, mid_term: MidTermMemory, long_term: LongTermMemory):
        self.short_term = short_term
        self.mid_term = mid_term
        self.long_term = long_term
        self.consolidation_counter = 0
        self.last_consolidation = datetime.now()
    
    def should_consolidate(self, interaction_count: int) -> bool:
        """Determine if consolidation should occur"""
        return (
            interaction_count % 10 == 0 or  # Every 10 interactions
            datetime.now() - self.last_consolidation > timedelta(hours=1)  # Or every hour
        )
    
    def consolidate_memories(self, user_id: str):
        """Perform memory consolidation"""
        logger.info(f"Starting memory consolidation for user {user_id}")
        
        try:
            # 1. Consolidate short-term to mid-term
            self._consolidate_short_to_mid()
            
            # 2. Extract patterns for long-term storage
            self._extract_patterns_to_long_term(user_id)
            
            # 3. Update user profile
            self._update_user_profile(user_id)
            
            # 4. Optimize response strategies
            self._optimize_response_strategies(user_id)
            
            self.last_consolidation = datetime.now()
            self.consolidation_counter += 1
            
            logger.info(f"Memory consolidation completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error during memory consolidation: {e}")
    
    def _consolidate_short_to_mid(self):
        """Consolidate key insights from short-term to mid-term memory"""
        # Extract key insights from recent conversations
        recent_exchanges = self.short_term.get_recent_context(10)
        
        for exchange in recent_exchanges:
            # Create insight from high-confidence exchanges
            if exchange.confidence > 0.8:
                insight = MemoryEntry(
                    timestamp=exchange.timestamp,
                    content={
                        'intent': exchange.intent,
                        'entities': exchange.entities,
                        'context': exchange.context,
                        'user_message': exchange.user_message[:200],  # Truncate for storage
                        'confidence': exchange.confidence
                    },
                    importance=exchange.confidence,
                    tags=['conversation', 'high_confidence', exchange.intent]
                )
                
                self.mid_term.add_insight(insight)
        
        # Consolidate task context
        if self.short_term.current_task_context:
            self.mid_term.project_knowledge['current_session'] = self.short_term.current_task_context
        
        # Consolidate corrections
        if self.short_term.corrections:
            for correction in self.short_term.corrections:
                self.mid_term.record_decision({
                    'type': 'user_correction',
                    'correction': correction,
                    'importance': 0.8
                })
    
    def _extract_patterns_to_long_term(self, user_id: str):
        """Extract patterns for long-term storage"""
        # Extract workflow patterns
        for pattern_name, steps in self.mid_term.workflow_patterns.items():
            if len(steps) >= 3:  # Only patterns with sufficient data
                self.long_term.add_historical_pattern(
                    f"workflow_{pattern_name}",
                    {
                        'user_id': user_id,
                        'steps': steps,
                        'frequency': len(steps),
                        'session_id': self.mid_term.session_id
                    }
                )
        
        # Extract domain knowledge from insights
        for insight in self.mid_term.session_insights:
            if insight.importance > 0.7:
                domain = insight.tags[0] if insight.tags else 'general'
                self.long_term.add_domain_knowledge(
                    domain,
                    insight.content,
                    insight.importance
                )
        
        # Extract optimization patterns
        for decision in self.mid_term.decision_history:
            if decision.get('type') == 'optimization':
                self.long_term.add_optimization_pattern(
                    decision.get('category', 'general'),
                    {
                        'user_id': user_id,
                        'decision': decision,
                        'session_id': self.mid_term.session_id
                    }
                )
    
    def _update_user_profile(self, user_id: str):
        """Update user profile with new preferences and patterns"""
        profile_updates = {}
        
        # Update expertise level based on interactions
        if self.mid_term.session_insights:
            avg_confidence = sum(i.importance for i in self.mid_term.session_insights) / len(self.mid_term.session_insights)
            if avg_confidence > 0.8:
                profile_updates['expertise_level'] = 'expert'
            elif avg_confidence > 0.6:
                profile_updates['expertise_level'] = 'intermediate'
            else:
                profile_updates['expertise_level'] = 'beginner'
        
        # Update common tasks
        task_patterns = list(self.mid_term.workflow_patterns.keys())
        if task_patterns:
            profile_updates['common_tasks'] = task_patterns
        
        # Update template preferences
        if self.mid_term.template_customizations:
            profile_updates['template_preferences'] = self.mid_term.template_customizations
        
        # Update workflow patterns
        workflow_freq = {}
        for pattern, steps in self.mid_term.workflow_patterns.items():
            workflow_freq[pattern] = len(steps)
        if workflow_freq:
            profile_updates['workflow_patterns'] = workflow_freq
        
        # Apply updates
        if profile_updates:
            self.long_term.update_user_profile(user_id, profile_updates)
    
    def _optimize_response_strategies(self, user_id: str):
        """Optimize response strategies based on accumulated learning"""
        profile = self.long_term.get_user_profile(user_id)
        
        # Analyze successful interactions
        successful_patterns = []
        for insight in self.mid_term.session_insights:
            if insight.importance > 0.8:
                successful_patterns.append({
                    'intent': insight.content.get('intent'),
                    'confidence': insight.content.get('confidence'),
                    'context': insight.content.get('context', {})
                })
        
        if successful_patterns:
            self.long_term.add_optimization_pattern(
                'response_strategy',
                {
                    'user_id': user_id,
                    'successful_patterns': successful_patterns,
                    'expertise_level': profile.expertise_level,
                    'communication_style': profile.communication_style
                }
            )

class AdvancedMemoryManager:
    """Main memory management system coordinating all memory levels"""
    
    def __init__(self, storage_path: str = "instance/memory"):
        self.short_term = ShortTermMemory()
        self.mid_term = MidTermMemory()
        self.long_term = LongTermMemory(storage_path)
        self.consolidation = MemoryConsolidationProtocol(
            self.short_term, self.mid_term, self.long_term
        )
        self.interaction_count = 0
        
    def initialize_session(self, user_id: str, session_id: str):
        """Initialize memory system for a new session"""
        self.mid_term.start_session(session_id)
        
        # Load user profile to inform session
        profile = self.long_term.get_user_profile(user_id)
        
        # Initialize mid-term memory with user preferences
        self.mid_term.user_preferences = {
            'expertise_level': profile.expertise_level,
            'communication_style': profile.communication_style,
            'detail_level': profile.preferred_detail_level,
            'common_tasks': profile.common_tasks,
            'template_preferences': profile.template_preferences
        }
        
        logger.info(f"Memory system initialized for user {user_id}, session {session_id}")
    
    def process_interaction(self, user_id: str, user_message: str, agent_response: str, 
                          intent: str, entities: Dict[str, Any], context: Dict[str, Any], 
                          confidence: float, task_context: Optional[str] = None):
        """Process a complete interaction through the memory system"""
        
        # Create conversation exchange
        exchange = ConversationExchange(
            user_message=user_message,
            agent_response=agent_response,
            intent=intent,
            entities=entities,
            context=context,
            timestamp=datetime.now(),
            confidence=confidence,
            task_context=task_context
        )
        
        # Add to short-term memory
        self.short_term.add_exchange(exchange)
        
        # Update task context if provided
        if task_context:
            self.short_term.update_task_context({'current_task': task_context})
        
        # Increment interaction count
        self.interaction_count += 1
        
        # Check if consolidation is needed
        if self.consolidation.should_consolidate(self.interaction_count):
            self.consolidation.consolidate_memories(user_id)
    
    def add_user_correction(self, correction: Dict[str, Any]):
        """Add user correction to memory"""
        self.short_term.add_correction(correction)
    
    def get_contextual_memory(self, user_id: str, query_tags: List[str] = None) -> Dict[str, Any]:
        """Get comprehensive contextual memory for response generation"""
        
        # Get user profile
        profile = self.long_term.get_user_profile(user_id)
        
        # Get short-term context
        short_term_context = self.short_term.get_active_context()
        
        # Get mid-term insights
        mid_term_summary = self.mid_term.get_session_summary()
        
        # Get relevant long-term knowledge
        relevant_knowledge = []
        if query_tags:
            relevant_knowledge = self.long_term.get_relevant_knowledge(query_tags, limit=5)
        
        return {
            'user_profile': asdict(profile),
            'short_term': short_term_context,
            'mid_term': mid_term_summary,
            'relevant_knowledge': [asdict(entry) for entry in relevant_knowledge],
            'interaction_count': self.interaction_count,
            'consolidation_count': self.consolidation.consolidation_counter
        }
    
    def get_memory_influenced_response_context(self, user_id: str, current_intent: str) -> Dict[str, Any]:
        """Get memory-influenced context for response generation"""
        
        profile = self.long_term.get_user_profile(user_id)
        recent_context = self.short_term.get_recent_context(3)
        
        # Build context based on memory
        context = {
            'user_expertise': profile.expertise_level,
            'communication_style': profile.communication_style,
            'preferred_detail_level': profile.preferred_detail_level,
            'recent_interactions': [
                {
                    'intent': ex.intent,
                    'confidence': ex.confidence,
                    'task_context': ex.task_context
                } for ex in recent_context
            ],
            'common_tasks': profile.common_tasks,
            'workflow_patterns': profile.workflow_patterns,
            'template_preferences': profile.template_preferences,
            'current_task': self.short_term.current_task_context.get('current_task'),
            'active_parameters': self.short_term.active_parameters,
            'recent_corrections': self.short_term.corrections[-2:] if self.short_term.corrections else []
        }
        
        # Add relevant historical patterns
        if current_intent in self.long_term.historical_patterns:
            pattern_data = self.long_term.historical_patterns[current_intent]
            context['historical_pattern'] = {
                'occurrences': pattern_data['occurrences'],
                'success_rate': pattern_data.get('success_rate', 0.8),
                'common_parameters': pattern_data.get('common_parameters', {})
            }
        
        return context
    
    def end_session(self, user_id: str):
        """End session and perform final consolidation"""
        logger.info(f"Ending session for user {user_id}")
        
        # Perform final consolidation
        self.consolidation.consolidate_memories(user_id)
        
        # Update global statistics
        session_stats = {
            'total_interactions': self.interaction_count,
            'session_duration': datetime.now() - self.mid_term.session_start,
            'consolidations_performed': self.consolidation.consolidation_counter,
            'insights_generated': len(self.mid_term.session_insights)
        }
        
        self.long_term.update_global_statistics({
            f'session_{self.mid_term.session_id}': session_stats,
            'last_session_end': datetime.now()
        })
        
        # Reset for next session
        self.interaction_count = 0
        self.short_term = ShortTermMemory()
        self.mid_term = MidTermMemory()

# Global memory manager instance
memory_manager = AdvancedMemoryManager()

# Public interface functions
def initialize_memory_session(user_id: str, session_id: str):
    """Initialize memory system for a new session"""
    return memory_manager.initialize_session(user_id, session_id)

def process_memory_interaction(user_id: str, user_message: str, agent_response: str,
                             intent: str, entities: Dict[str, Any], context: Dict[str, Any],
                             confidence: float, task_context: Optional[str] = None):
    """Process interaction through memory system"""
    return memory_manager.process_interaction(
        user_id, user_message, agent_response, intent, entities, 
        context, confidence, task_context
    )

def get_memory_context(user_id: str, query_tags: List[str] = None) -> Dict[str, Any]:
    """Get comprehensive memory context"""
    return memory_manager.get_contextual_memory(user_id, query_tags)

def get_response_context(user_id: str, current_intent: str) -> Dict[str, Any]:
    """Get memory-influenced response context"""
    return memory_manager.get_memory_influenced_response_context(user_id, current_intent)

def add_memory_correction(correction: Dict[str, Any]):
    """Add user correction to memory"""
    return memory_manager.add_user_correction(correction)

def end_memory_session(user_id: str):
    """End memory session"""
    return memory_manager.end_session(user_id)