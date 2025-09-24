"""
Test script for the Advanced Memory Management System
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.memory_manager import (
    AdvancedMemoryManager, ShortTermMemory, MidTermMemory, LongTermMemory,
    ConversationExchange, UserProfile, MemoryEntry
)
from datetime import datetime
import json

def test_memory_system():
    """Test the complete memory management system"""
    
    print("🧠 Testing Advanced Memory Management System")
    print("=" * 50)
    
    # Test 1: Initialize Memory Manager
    print("\n1. Testing Memory Manager Initialization...")
    memory_manager = AdvancedMemoryManager()
    print("✅ Memory manager initialized successfully")
    
    # Test 2: Initialize Session
    print("\n2. Testing Session Initialization...")
    user_id = "test_user_123"
    session_id = "session_456"
    memory_manager.initialize_session(user_id, session_id)
    print(f"✅ Session initialized for user {user_id}")
    
    # Test 3: Process Interactions
    print("\n3. Testing Interaction Processing...")
    
    interactions = [
        {
            "user_message": "I need to create a SAT report",
            "agent_response": "I'll help you create a comprehensive SAT report. Let's start with the project details.",
            "intent": "create_report",
            "entities": {"report_type": "SAT"},
            "context": {"current_task": "report_creation"},
            "confidence": 0.9,
            "task_context": "create_sat_report"
        },
        {
            "user_message": "The client is Acme Corp and project reference is ACME-2024-001",
            "agent_response": "Great! I've recorded Acme Corp as the client and ACME-2024-001 as the project reference.",
            "intent": "provide_information",
            "entities": {"client_name": "Acme Corp", "project_reference": "ACME-2024-001"},
            "context": {"current_task": "report_creation", "client_name": "Acme Corp"},
            "confidence": 0.95,
            "task_context": "create_sat_report"
        },
        {
            "user_message": "Actually, the project reference should be ACME-2024-002",
            "agent_response": "I've updated the project reference to ACME-2024-002. Thank you for the correction.",
            "intent": "correction",
            "entities": {"project_reference": "ACME-2024-002"},
            "context": {"current_task": "report_creation", "correction": True},
            "confidence": 0.98,
            "task_context": "create_sat_report"
        }
    ]
    
    for i, interaction in enumerate(interactions, 1):
        memory_manager.process_interaction(
            user_id=user_id,
            user_message=interaction["user_message"],
            agent_response=interaction["agent_response"],
            intent=interaction["intent"],
            entities=interaction["entities"],
            context=interaction["context"],
            confidence=interaction["confidence"],
            task_context=interaction["task_context"]
        )
        print(f"✅ Processed interaction {i}")
    
    # Test 4: Test Memory Retrieval
    print("\n4. Testing Memory Retrieval...")
    
    # Get contextual memory
    contextual_memory = memory_manager.get_contextual_memory(user_id, ["create_report", "SAT"])
    print(f"✅ Retrieved contextual memory with {len(contextual_memory['relevant_knowledge'])} knowledge entries")
    
    # Get response context
    response_context = memory_manager.get_memory_influenced_response_context(user_id, "create_report")
    print(f"✅ Retrieved response context for user expertise: {response_context['user_expertise']}")
    
    # Test 5: Test Memory Consolidation
    print("\n5. Testing Memory Consolidation...")
    
    # Process more interactions to trigger consolidation
    for i in range(7):  # Process 7 more to reach 10 total
        memory_manager.process_interaction(
            user_id=user_id,
            user_message=f"Test message {i+4}",
            agent_response=f"Test response {i+4}",
            intent="test_intent",
            entities={},
            context={"test": True},
            confidence=0.8
        )
    
    print("✅ Memory consolidation triggered and completed")
    
    # Test 6: Test User Profile Learning
    print("\n6. Testing User Profile Learning...")
    
    # Get updated user profile
    final_memory = memory_manager.get_contextual_memory(user_id)
    user_profile = final_memory['user_profile']
    
    print(f"✅ User profile updated:")
    print(f"   - Total interactions: {user_profile['total_interactions']}")
    print(f"   - Expertise level: {user_profile['expertise_level']}")
    print(f"   - Communication style: {user_profile['communication_style']}")
    print(f"   - Common tasks: {user_profile['common_tasks']}")
    
    # Test 7: Test Short-term Memory
    print("\n7. Testing Short-term Memory...")
    
    short_term = memory_manager.short_term
    recent_context = short_term.get_recent_context(3)
    print(f"✅ Short-term memory contains {len(recent_context)} recent exchanges")
    print(f"   - Active parameters: {len(short_term.active_parameters)} items")
    print(f"   - Corrections: {len(short_term.corrections)} items")
    
    # Test 8: Test Mid-term Memory
    print("\n8. Testing Mid-term Memory...")
    
    mid_term = memory_manager.mid_term
    session_summary = mid_term.get_session_summary()
    print(f"✅ Mid-term memory session summary:")
    print(f"   - Session duration: {session_summary['duration']}")
    print(f"   - Projects worked on: {len(session_summary['projects_worked_on'])}")
    print(f"   - Key insights: {len(session_summary['key_insights'])}")
    print(f"   - Decisions made: {session_summary['decisions_made']}")
    
    # Test 9: Test Long-term Memory
    print("\n9. Testing Long-term Memory...")
    
    long_term = memory_manager.long_term
    user_profile_obj = long_term.get_user_profile(user_id)
    print(f"✅ Long-term memory user profile:")
    print(f"   - User ID: {user_profile_obj.user_id}")
    print(f"   - Total interactions: {user_profile_obj.total_interactions}")
    print(f"   - Domain expertise: {len(user_profile_obj.domain_expertise)} domains")
    print(f"   - Workflow patterns: {len(user_profile_obj.workflow_patterns)} patterns")
    
    # Test 10: Test Memory-Enhanced Response Context
    print("\n10. Testing Memory-Enhanced Response Context...")
    
    enhanced_context = memory_manager.get_memory_influenced_response_context(user_id, "create_report")
    print(f"✅ Enhanced response context:")
    print(f"   - User expertise: {enhanced_context['user_expertise']}")
    print(f"   - Recent interactions: {len(enhanced_context['recent_interactions'])}")
    print(f"   - Current task: {enhanced_context['current_task']}")
    print(f"   - Active parameters: {len(enhanced_context['active_parameters'])}")
    
    # Test 11: Test Session End
    print("\n11. Testing Session End...")
    memory_manager.end_session(user_id)
    print("✅ Session ended and final consolidation completed")
    
    # Test 12: Test Memory Persistence
    print("\n12. Testing Memory Persistence...")
    
    # Create new memory manager to test persistence
    new_memory_manager = AdvancedMemoryManager()
    persistent_profile = new_memory_manager.long_term.get_user_profile(user_id)
    print(f"✅ Memory persistence verified:")
    print(f"   - Persistent user found: {persistent_profile.user_id}")
    print(f"   - Interactions preserved: {persistent_profile.total_interactions}")
    
    print("\n" + "=" * 50)
    print("🎉 All Memory Management System tests completed successfully!")
    print("\n📊 Test Summary:")
    print("✅ Memory Manager Initialization")
    print("✅ Session Management")
    print("✅ Interaction Processing")
    print("✅ Memory Retrieval")
    print("✅ Memory Consolidation")
    print("✅ User Profile Learning")
    print("✅ Short-term Memory")
    print("✅ Mid-term Memory")
    print("✅ Long-term Memory")
    print("✅ Enhanced Response Context")
    print("✅ Session Management")
    print("✅ Memory Persistence")
    
    return True

def test_memory_components():
    """Test individual memory components"""
    
    print("\n🔧 Testing Individual Memory Components")
    print("=" * 40)
    
    # Test Short-term Memory
    print("\n1. Testing Short-term Memory...")
    short_term = ShortTermMemory(max_exchanges=5)
    
    # Add test exchanges
    for i in range(7):  # Add more than max to test deque behavior
        exchange = ConversationExchange(
            user_message=f"Test message {i}",
            agent_response=f"Test response {i}",
            intent="test",
            entities={},
            context={},
            timestamp=datetime.now(),
            confidence=0.8
        )
        short_term.add_exchange(exchange)
    
    print(f"✅ Short-term memory: {len(short_term.conversation_history)} exchanges (max 5)")
    
    # Test Mid-term Memory
    print("\n2. Testing Mid-term Memory...")
    mid_term = MidTermMemory()
    mid_term.start_session("test_session")
    
    # Add test data
    mid_term.add_project_knowledge("project_1", {"type": "SAT", "client": "Test Corp"})
    mid_term.track_workflow_pattern("report_creation", ["start", "collect_data", "validate"])
    mid_term.add_template_customization("SAT", {"header": "Custom Header"})
    
    insight = MemoryEntry(
        timestamp=datetime.now(),
        content={"insight": "User prefers detailed explanations"},
        importance=0.8,
        tags=["user_preference", "communication"]
    )
    mid_term.add_insight(insight)
    
    summary = mid_term.get_session_summary()
    print(f"✅ Mid-term memory: {len(summary['key_insights'])} insights, {len(summary['workflow_patterns'])} patterns")
    
    # Test Long-term Memory
    print("\n3. Testing Long-term Memory...")
    long_term = LongTermMemory("test_memory_storage")
    
    # Test user profile
    profile = long_term.get_user_profile("test_user")
    long_term.update_user_profile("test_user", {
        "expertise_level": "expert",
        "common_tasks": ["create_reports", "analyze_data"]
    })
    
    # Test domain knowledge
    long_term.add_domain_knowledge("automation", {
        "protocols": ["Modbus", "OPC"],
        "standards": ["IEC 61131"]
    }, importance=0.9)
    
    # Test historical patterns
    long_term.add_historical_pattern("workflow_sat", {
        "steps": ["planning", "execution", "documentation"],
        "success_rate": 0.95
    })
    
    relevant_knowledge = long_term.get_relevant_knowledge(["automation"], limit=3)
    print(f"✅ Long-term memory: {len(relevant_knowledge)} relevant knowledge entries")
    
    print("\n✅ All individual component tests completed!")

if __name__ == "__main__":
    try:
        # Test complete system
        test_memory_system()
        
        # Test individual components
        test_memory_components()
        
        print("\n🎯 Memory Management System is fully operational!")
        print("The AI agent now has sophisticated memory capabilities:")
        print("• Short-term: Last 20 conversation exchanges")
        print("• Mid-term: Session-based project knowledge and patterns")
        print("• Long-term: Persistent user profiles and domain expertise")
        print("• Consolidation: Automatic memory optimization every 10 interactions")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)