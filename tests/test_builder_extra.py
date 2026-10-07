import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import importlib

import cml_parser

# Ensure we are using the in-repo package (not an older installed one)
assert hasattr(cml_parser, "parse_text"), cml_parser.__file__
parse_text = cml_parser.parse_text


def test_builder_covers_modules_usecases_and_values():
    cml = r'''
    ContextMap Map { contains BC }
    BoundedContext BC {
      type = FEATURE
      knowledgeLevel = META
      responsibilities = "Keep things"
      implementationTechnology = "Python"

      Module Mod {
        Entity Orphan {}
        ValueObject Alias extends @Base {}
        DomainEvent Event extends BaseEvent { aggregateRoot persistent String id key }
        enum States { A, B }
        Service PlainService { void ping(); }
      }

      Aggregate Agg {
        owner OwnerTeam
        ValueObject OrderId { String id key }
        Service OrderService { void op(); }
        Repository OrderRepo { String find(@OrderId id); }
      }

      Application App {
        command Place
        flow SimpleFlow { command Place }
        coordination SimpleCoord { step1 step2 }
      }
    }

    Domain D {
      Subdomain S { type SUPPORTING_DOMAIN domainVisionStatement = "Vision" }
    }

    UseCase Pay {
      actor "User"
      benefit "Fast"
      scope "Checkout"
      level "Summary"
      interactions read "data" with its "type", "extra"
    }

    UserStory Story {
      As "Role"
      I want to "do something"
      so that "value"
    }

    Stakeholders of Project {
      StakeholderGroup Users {
        Stakeholder Admin {
          influence High
          interest Low
          priority Medium
          impact High
        }
      }
    }

    ValueRegister Reg for Project {
      ValueCluster Core {
        core CoreValue
        demonstrator "Demo"
        Value Benefit { isCore Stakeholder Admin {} }
      }
      Value Extra { demonstrator "Note" }
    }
    '''

    model = parse_text(cml, strict=True)

    # Bounded context level attributes
    bc = model.get_context("BC")
    assert bc.type == "FEATURE"
    assert bc.knowledge_level == "META"
    assert bc.responsibilities == "Keep things"
    assert bc.implementation_technology == "Python"

    # Module domain objects and enum
    mod = bc.modules[0]
    names = {obj.name for obj in mod.domain_objects}
    assert {"Orphan", "Alias", "Event", "States"}.issubset(names)

    # ValueObject extends
    alias = next(obj for obj in mod.domain_objects if obj.name == "Alias")
    assert alias.extends == "Base"

    # DomainEvent flags and key attribute
    event = next(obj for obj in mod.domain_objects if obj.name == "Event")
    assert event.extends == "BaseEvent"
    assert event.is_aggregate_root is True
    assert event.persistent is True
    assert any(attr.is_key for attr in event.attributes)

    # Service under module keeps operations
    svc = next(obj for obj in mod.services if obj.name == "PlainService")
    assert svc.operations[0].name == "ping"

    # Aggregate content and repository
    agg = bc.get_aggregate("Agg")
    assert agg.owner == "OwnerTeam"
    repo = agg.repositories[0]
    assert repo.operations[0].name == "find"
    assert repo.operations[0].parameters[0].is_reference is True

    # Subdomain attribute handling
    sd = model.get_subdomain("S")
    assert sd.type.value == "SUPPORTING_DOMAIN"
    assert sd.vision == "Vision"

    # Use case and user story parsing
    uc = model.use_cases[0]
    assert uc.actor == "User" and "data" in uc.interactions[0]
    us = model.user_stories[0]
    assert us.role == "Role" and us.feature == "do something" and us.benefit == "value"

    # Stakeholder group attributes
    group = model.stakeholder_groups[0]
    admin = group.stakeholders[0]
    assert admin.influence == "High"
    assert admin.interest == "Low"
    assert admin.priority == "Medium"
    assert admin.impact == "High"

    # Value register with cluster and value stakeholders
    reg = model.value_registers[0]
    cluster = reg.clusters[0]
    assert cluster.core_value == "CoreValue"
    assert cluster.demonstrator == "Demo"
    val = cluster.values[0]
    assert val.is_core is True
    assert val.stakeholders[0].name == "Admin"
