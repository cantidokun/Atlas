"""Integration tests for the Atlas ↔ Unreal production transport.

These tests verify the complete transport pipeline including:
- Named pipe connectivity
- Request/response serialization
- Unreal Editor integration
- Actor inspection functionality
"""

import pytest
from unittest.mock import Mock, patch

from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse
from planning.unreal_agent import UnrealOperation, UnrealCapability, UnrealOperationKind

# Import production components
try:
    from planning.unreal_transport_named_pipe import (
        WindowsNamedPipeTransport,
        NamedPipeTransportError,
        create_named_pipe_transport,
    )
    from planning.unreal_adapter_production import create_production_adapter
    TRANSPORT_AVAILABLE = True
except ImportError:
    TRANSPORT_AVAILABLE = False


@pytest.mark.skipif(not TRANSPORT_AVAILABLE, reason="Named pipe transport not available")
class TestNamedPipeTransport:
    """Test the Windows named pipe transport implementation."""
    
    def test_transport_creation(self):
        """Test that transport can be created."""
        transport = create_named_pipe_transport()
        assert isinstance(transport, WindowsNamedPipeTransport)
        assert transport.pipe_name == r"\\.\pipe\AtlasUnrealTransport"
    
    def test_transport_creation_custom_pipe(self):
        """Test transport creation with custom pipe name."""
        custom_pipe = r"\\.\pipe\TestPipe"
        transport = create_named_pipe_transport(custom_pipe)
        assert transport.pipe_name == custom_pipe
    
    def test_send_requires_transport_request(self):
        """Test that send() validates input type."""
        transport = create_named_pipe_transport()
        
        with pytest.raises(TypeError, match="UnrealTransportRequest"):
            transport.send({"not": "a request"})
    
    def test_send_unavailable_server(self):
        """Test behavior when Unreal server is not available."""
        transport = create_named_pipe_transport()
        
        request = UnrealTransportRequest(
            request_id="test-001",
            operation_name="inspect_target_actors",
            capability="inspect_actor",
            kind="read",
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
            authorization_id="auth-test-123",
        )
        
        with pytest.raises(NamedPipeTransportError, match="not available"):
            transport.send(request)


@pytest.mark.skipif(not TRANSPORT_AVAILABLE, reason="Named pipe transport not available")
class TestProductionAdapter:
    """Test the production adapter with named pipe transport."""
    
    def test_adapter_creation(self):
        """Test that production adapter can be created."""
        adapter = create_production_adapter()
        assert adapter._source_tag == "atlas-adapter-production"
    
    def test_adapter_creation_custom_source(self):
        """Test adapter creation with custom source tag."""
        adapter = create_production_adapter("custom-source")
        assert adapter._source_tag == "custom-source"
    
    def test_inspect_operation_validation(self):
        """Test that inspect validates operation kind."""
        adapter = create_production_adapter()
        
        # Create a WRITE operation (should be rejected)
        write_operation = UnrealOperation(
            name="invalid_write",
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.WRITE,
            arguments={},
            entity_ids=("TEST",),
        )
        
        with pytest.raises(Exception, match="READ operations only"):
            adapter.inspect(write_operation, "auth-123")


class TestTransportIntegration:
    """Integration tests that can run without Unreal Editor."""
    
    def test_request_serialization_compatibility(self):
        """Test that our serialization matches expected format."""
        from planning.unreal_transport_serialization import serialize_request
        
        request = UnrealTransportRequest(
            request_id="req-001",
            operation_name="inspect_target_actors",
            capability="inspect_actor",
            kind="read",
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
            authorization_id="auth-abc-123",
        )
        
        json_str = serialize_request(request)
        
        # Verify it's valid JSON and contains expected fields
        import json
        data = json.loads(json_str)
        
        assert data["request_id"] == "req-001"
        assert data["operation_name"] == "inspect_target_actors"
        assert data["capability"] == "inspect_actor"
        assert data["kind"] == "read"
        assert data["entity_ids"] == ["FIELD_SURFACE"]
        assert data["authorization_id"] == "auth-abc-123"
        assert data["arguments"]["entity_ids"] == ["FIELD_SURFACE"]
    
    def test_response_deserialization_compatibility(self):
        """Test that we can deserialize expected response format."""
        from planning.unreal_transport_serialization import deserialize_response
        
        response_json = """{
            "request_id": "req-001",
            "operation_name": "inspect_target_actors",
            "entity_ids": ["FIELD_SURFACE"],
            "success": true,
            "observed_state": {
                "FIELD_SURFACE": {
                    "entity_id": "FIELD_SURFACE",
                    "actor_name": "TestActor",
                    "actor_class": "StaticMeshActor",
                    "location": {"x": 100.0, "y": 200.0, "z": 300.0},
                    "rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0}
                }
            },
            "error": "",
            "source": "unreal-editor-atlas-transport"
        }"""
        
        response = deserialize_response(response_json)
        
        assert response.request_id == "req-001"
        assert response.operation_name == "inspect_target_actors"
        assert response.entity_ids == ("FIELD_SURFACE",)
        assert response.success is True
        assert response.error == ""
        assert response.source == "unreal-editor-atlas-transport"
        
        # Verify observed state structure
        observed = response.observed_state
        assert "FIELD_SURFACE" in observed
        
        field_data = observed["FIELD_SURFACE"]
        assert field_data["entity_id"] == "FIELD_SURFACE"
        assert field_data["actor_name"] == "TestActor"
        assert field_data["actor_class"] == "StaticMeshActor"
        
        location = field_data["location"]
        assert location["x"] == 100.0
        assert location["y"] == 200.0
        assert location["z"] == 300.0
        
        rotation = field_data["rotation"]
        assert rotation["pitch"] == 0.0
        assert rotation["yaw"] == 90.0
        assert rotation["roll"] == 0.0
    
    def test_malformed_request_rejection(self):
        """Test that malformed requests are rejected."""
        from planning.unreal_transport_serialization import deserialize_request, TransportDeserializationError
        
        # Missing required field
        with pytest.raises(TransportDeserializationError, match="missing keys"):
            deserialize_request('{"request_id": "test"}')
        
        # Extra field
        with pytest.raises(TransportDeserializationError, match="extra keys"):
            deserialize_request('''{
                "request_id": "test",
                "operation_name": "inspect_target_actors",
                "capability": "inspect_actor",
                "kind": "read",
                "arguments": {},
                "entity_ids": [],
                "authorization_id": "auth",
                "extra_field": "not allowed"
            }''')
        
        # Invalid JSON
        with pytest.raises(TransportDeserializationError, match="not valid JSON"):
            deserialize_request('{invalid json}')
    
    def test_unsupported_operation_handling(self):
        """Test handling of unsupported operations."""
        # This would be tested with a mock transport that simulates
        # the Unreal side rejecting unsupported operations
        pass
    
    def test_authorization_validation(self):
        """Test that authorization_id is properly validated."""
        from planning.unreal_transport_serialization import deserialize_request, TransportDeserializationError
        
        # Empty authorization_id should be caught by UnrealTransportRequest.__post_init__
        with pytest.raises(ValueError, match="authorization_id"):
            deserialize_request('''{
                "request_id": "test",
                "operation_name": "inspect_target_actors",
                "capability": "inspect_actor",
                "kind": "read",
                "arguments": {},
                "entity_ids": ["TEST"],
                "authorization_id": ""
            }''')


@pytest.mark.integration
@pytest.mark.skipif(not TRANSPORT_AVAILABLE, reason="Named pipe transport not available")
class TestRealUnrealIntegration:
    """Integration tests that require a running Unreal Editor.
    
    These tests are marked with @pytest.mark.integration and will only
    run when explicitly requested and when Unreal Editor is available.
    """
    
    def test_real_unreal_connection(self):
        """Test actual connection to running Unreal Editor.
        
        This test distinguishes between:
        A. Transport unavailable (Unreal not running)
        B. Transport available but entity not found
        C. Successful inspection
        """
        adapter = create_production_adapter("integration-test")
        
        operation = UnrealOperation(
            name="inspect_target_actors",
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
        )
        
        try:
            evidence = adapter.inspect(operation, "integration-test-auth-001")
            
            # If we get here, Unreal is running and responded
            assert evidence.operation_name == "inspect_target_actors"
            assert evidence.entity_ids == ("FIELD_SURFACE",)
            assert evidence.verified is False  # Never verified by transport
            assert evidence.source.startswith("unreal-editor")
            
            # Check observed state structure
            observed = evidence.observed_state
            if evidence.verified:  # This should never happen
                pytest.fail("Transport incorrectly set verified=True")
            
            print(f"✓ Real Unreal integration successful: {evidence.source}")
            print(f"✓ Observed state keys: {list(observed.keys())}")
            
        except NamedPipeTransportError as e:
            if "not available" in str(e):
                pytest.skip("Unreal Editor not running - cannot test real integration")
            elif "not found" in str(e):
                pytest.skip("FIELD_SURFACE entity not found in Unreal - setup required")
            else:
                raise
    
    def test_sequential_requests(self):
        """Test that multiple sequential requests work (pipe lifecycle)."""
        adapter = create_production_adapter("sequential-test")
        
        operation = UnrealOperation(
            name="inspect_target_actors",
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            arguments={"entity_ids": ("FIELD_SURFACE",)},
            entity_ids=("FIELD_SURFACE",),
        )
        
        try:
            # First request
            evidence1 = adapter.inspect(operation, "sequential-test-auth-001")
            assert evidence1.operation_name == "inspect_target_actors"
            
            # Second request (tests pipe recreation)
            evidence2 = adapter.inspect(operation, "sequential-test-auth-002")
            assert evidence2.operation_name == "inspect_target_actors"
            
            print("✓ Sequential requests successful")
            
        except NamedPipeTransportError as e:
            if "not available" in str(e):
                pytest.skip("Unreal Editor not running - cannot test sequential requests")
            else:
                raise
