"""Test Pydantic models"""

import pytest
from pydantic import ValidationError
from src.models.chart import (
    ChartRequest,
    TypeInfo,
    AuthorityInfo,
    ProfileInfo,
    Center,
    Channel,
    Gate,
    IncarnationCross,
    ChartResponse
)


class TestChartRequest:
    """Test ChartRequest model"""

    def test_valid_chart_request(self):
        """Test valid chart request creation"""
        request = ChartRequest(
            firstName="John",
            birthDate="15.06.1990",
            birthTime="14:30",
            birthTimeApproximate=False,
            birthPlace="Berlin, Germany"
        )

        assert request.firstName == "John"
        assert request.birthDate == "15.06.1990"
        assert request.birthTime == "14:30"
        assert request.birthPlace == "Berlin, Germany"

    def test_approximate_time_without_time(self):
        """Test chart request with approximate time but no time specified"""
        request = ChartRequest(
            firstName="John",
            birthDate="15.06.1990",
            birthTimeApproximate=True,
            birthPlace="Berlin, Germany"
        )

        assert request.birthTimeApproximate is True
        assert request.birthTime is None

    def test_name_too_short(self):
        """Test chart request with name too short"""
        with pytest.raises(ValidationError):
            ChartRequest(
                firstName="A",  # Too short
                birthDate="15.06.1990",
                birthTime="14:30",
                birthPlace="Berlin, Germany"
            )

    def test_missing_required_fields(self):
        """Test chart request missing required fields"""
        with pytest.raises(ValidationError):
            ChartRequest(
                firstName="John"
                # Missing birthDate and birthPlace
            )


class TestChartResponse:
    """Test ChartResponse model"""

    def test_valid_chart_response(self):
        """Test valid chart response creation"""
        response = ChartResponse(
            firstName="John",
            type=TypeInfo(
                code="generator",
                label="Generator",
                shortDescription="Energy type"
            ),
            authority=AuthorityInfo(
                code="sacral",
                label="Sacral Authority",
                decisionHint="Trust your gut"
            ),
            profile=ProfileInfo(
                code="4/1",
                shortDescription="Opportunist/Investigator"
            ),
            centers=[
                Center(name="Sacral", code="sacral", defined=True),
                Center(name="Root", code="root", defined=False)
            ],
            channels=[
                Channel(code="34-20")
            ],
            gates={
                "conscious": [Gate(code="15.2")],
                "unconscious": [Gate(code="10.3")]
            },
            incarnationCross=IncarnationCross(
                code="LAX_Planning",
                name="Left Angle Cross of Planning",
                gates=["15", "10", "5", "35"]
            ),
            shortImpulse="Follow your sacral response"
        )

        assert response.firstName == "John"
        assert response.type.code == "generator"
        assert response.authority.code == "sacral"
        assert response.profile.code == "4/1"
        assert len(response.centers) == 2
        assert len(response.channels) == 1
        assert "conscious" in response.gates
        assert "unconscious" in response.gates


class TestTypeInfo:
    """Test TypeInfo model"""

    def test_create_type_info(self):
        """Test TypeInfo creation"""
        type_info = TypeInfo(
            code="manifestor",
            label="Manifestor",
            shortDescription="Initiator type"
        )

        assert type_info.code == "manifestor"
        assert type_info.label == "Manifestor"
        assert type_info.shortDescription == "Initiator type"


class TestCenter:
    """Test Center model"""

    def test_defined_center(self):
        """Test defined center"""
        center = Center(name="Sacral", code="sacral", defined=True, definitionType="defined")

        assert center.name == "Sacral"
        assert center.code == "sacral"
        assert center.defined is True
        assert center.definitionType == "defined"

    def test_undefined_center(self):
        """Test undefined center"""
        center = Center(name="Ego", code="ego", defined=False)

        assert center.name == "Ego"
        assert center.defined is False
        assert center.definitionType == "open"

    def test_unconsciously_defined_center(self):
        """Test center defined exclusively via Design (unconscious) gates"""
        center = Center(name="Spleen", code="spleen", defined=True, definitionType="unconscious")

        assert center.defined is True
        assert center.definitionType == "unconscious"
