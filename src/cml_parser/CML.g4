grammar CML;

/*
 * Context Mapper DSL (CML) Grammar for ANTLR4
 */

// --- Parser Rules ---

definitions
    : (imports | topLevel)* EOF
    ;

imports
    : 'import' STRING
    ;

topLevel
    : scUseCase
    | scAggregate
    | scEntity
    | scSecurityAccessGroup
    | scSeparatedSecurityZone
    | scSharedOwnerGroup
    | scPredefinedService
    | scCompatibilities
    | tacticDDDApplication
    | contextMap
    | boundedContext
    | domain
    | useCase
    | stakeholderSection
    | valueRegister
    | userStory
    ;

// --- Strategic DDD ---

contextMap
    : 'ContextMap' name? '{'
      contextMapSetting*
      relationship*
      '}'
    ;

contextMapSetting
    : 'type' '='? contextMapType
    | 'state' '='? contextMapState
    | 'contains' idList

    ;

contextMapType
    : 'UNDEFINED' | 'SYSTEM_LANDSCAPE' | 'ORGANIZATIONAL'
    ;

contextMapState
    : 'UNDEFINED' | 'AS_IS' | 'TO_BE'
    ;

relationship
    : relationshipEndpoint relationshipConnection relationshipEndpointRight (':' ID)? ('{' relationshipAttribute* '}')?
    ;

relationshipConnection
    : relationshipArrow | relationshipKeyword
    ;

relationshipEndpoint
    : relationshipRoles? name relationshipRoles?
    ;

relationshipEndpointRight
    : relationshipRoles? name ({self._input.LT(-1) is not None and self._input.LT(1).line == self._input.LT(-1).line}? relationshipRoles)?
    ;

relationshipKeyword
    : 'Customer-Supplier' | 'Supplier-Customer' | 'Upstream-Downstream' | 'Downstream-Upstream' | 'Partnership' | 'Shared-Kernel'
    ;

relationshipRoles
    : '[' relationshipRole (',' relationshipRole)* ']'
    ;

relationshipRole
    : 'ACL' | 'CF' | 'OHS' | 'PL' | 'SK' | 'U' | 'D' | 'S' | 'C' | 'P'
    ;

relationshipArrow
    : '<->' | '<-' | '->'
    ;

relationshipAttribute
    : 'implementationTechnology' '='? STRING
    | 'downstreamRights' '='? downstreamRights
    | 'exposedAggregates' '='? idList
    ;

downstreamRights
    : 'VETO_RIGHT' | 'INFLUENCER' | 'OPINION_LEADER' | 'DECISION_MAKER' | 'MONOPOLIST'
    ;

boundedContext
    : 'BoundedContext' name boundedContextLinkClause* body=contentBlock?
    ;

boundedContextLinkClause
    : 'implements' idList
    | 'realizes' idList
    | 'refines' name
    ;

boundedContextAttribute
    : 'type' '='? boundedContextType
    | 'domainVisionStatement' '='? STRING
    | 'implementationTechnology' '='? STRING
    | 'responsibilities' '='? STRING (',' STRING)*
    | 'knowledgeLevel' '='? knowledgeLevel
    | 'businessModel' '='? STRING
    | 'evolution' '='? evolutionType
    | 'realizes' '='? idList
    ;

boundedContextType
    : 'UNDEFINED' | 'FEATURE' | 'SYSTEM' | 'APPLICATION' | 'TEAM'
    ;

knowledgeLevel
    : 'META' | 'CONCRETE'
    ;

evolutionType
    : 'GENESIS' | 'CUSTOM_BUILT' | 'PRODUCT' | 'COMMODITY' | 'UNDEFINED'
    ;

domain
    : 'Domain' name body=contentBlock?
    ;

subdomain
    : 'Subdomain' name ('supports' idList)? body=contentBlock?
    ;

subdomainType
    : 'UNDEFINED' | 'CORE_DOMAIN' | 'SUPPORTING_DOMAIN' | 'GENERIC_SUBDOMAIN'
    ;

module
    : 'Module' name body=contentBlock?
    ;

// --- Tactic DDD (Sculptor) ---

tacticDDDApplication
    : STRING? 'TacticDDDApplication' name '{'
      'basePackage' '=' qualifiedName
      tacticDDDElement*
      '}'
    | STRING? 'ApplicationPart' name '{'
      tacticDDDElement*
      '}'
    ;

tacticDDDElement
    : service
    | resource
    | consumer
    | domainObject
    ;

aggregate
    : 'Aggregate' name body=contentBlock?
    ;

domainObject
    : STRING? simpleDomainObjectOrEnum
    ;

simpleDomainObjectOrEnum
    : simpleDomainObject | enumDecl
    ;

simpleDomainObject
    : entity
    | valueObject
    | domainEvent
    | commandEvent
    | dataTransferObject
    | trait
    | basicType
    ;

entity
    : 'abstract'? 'Entity' name ('extends' '@'? name)? ('with' traitRef (',' traitRef)*)* body=entityBody?
    ;

entityBody
    : '{'
      (entityFlag | feature)*
      '}'
    ;

entityFlag
    : 'belongsTo' ('@')? qualifiedName
    | 'validate' '=' STRING
    | 'package' '=' qualifiedName
    | 'inheritanceType' '=' STRING
    | 'discriminatorColumn' '=' STRING
    | 'discriminatorValue' '=' STRING
    | 'discriminatorType' '=' STRING
    | 'discriminatorLength' '=' STRING
    | 'databaseTable' '=' STRING
    | notPrefix? 'auditable'
    | notPrefix? 'optimisticLocking'
    | notPrefix? 'cache'
    | 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | notPrefix? 'immutable'
    | 'aggregateRoot'
    ;

valueObject
    : 'abstract'? 'ValueObject' name ('extends' '@'? name)? ('with' traitRef (',' traitRef)*)* body=valueObjectBody?
    ;

valueObjectBody
    : '{'
      valueObjectFlag*
      feature*
      '}'
    ;

valueObjectFlag
    : 'belongsTo' ('@')? qualifiedName
    | 'package' '=' qualifiedName
    | 'validate' '=' STRING
    | 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | notPrefix? 'immutable'
    | notPrefix? 'persistent'
    | notPrefix? 'cache'
    | notPrefix? 'optimisticLocking'
    | 'aggregateRoot'
    | 'databaseTable' '=' STRING
    | 'inheritanceType' '=' STRING
    | 'discriminatorColumn' '=' STRING
    | 'discriminatorValue' '=' STRING
    | 'discriminatorType' '=' STRING
    | 'discriminatorLength' '=' STRING
    ;

domainEvent
    : 'abstract'? ('DomainEvent' | 'Event') name ('extends' '@'? name)? ('with' traitRef (',' traitRef)*)* body=domainEventBody?
    ;

domainEventBody
    : '{'
      (domainEventFlag | feature)*
      '}'
    ;

domainEventFlag
    : 'belongsTo' ('@')? qualifiedName
    | 'package' '=' qualifiedName
    | 'validate' '=' STRING
    | 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | notPrefix? 'cache'
    | 'databaseTable' '=' STRING
    | 'inheritanceType' '=' STRING
    | 'discriminatorColumn' '=' STRING
    | 'discriminatorValue' '=' STRING
    | 'discriminatorType' '=' STRING
    | 'discriminatorLength' '=' STRING
    | 'aggregateRoot'
    | 'persistent'
    ;

commandEvent
    : 'abstract'? ('CommandEvent' | 'Command') name ('extends' '@'? name)? ('with' traitRef (',' traitRef)*)* body=commandEventBody?
    ;

commandEventBody
    : '{'
      commandEventFlag*
      feature*
      '}'
    ;

commandEventFlag
    : 'belongsTo' ('@')? qualifiedName
    | 'package' '=' qualifiedName
    | 'validate' '=' STRING
    | 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | notPrefix? 'cache'
    | 'persistent'
    | 'aggregateRoot'
    | 'databaseTable' '=' STRING
    | 'inheritanceType' '=' STRING
    | 'discriminatorColumn' '=' STRING
    | 'discriminatorValue' '=' STRING
    | 'discriminatorType' '=' STRING
    | 'discriminatorLength' '=' STRING
    ;

trait
    : 'Trait' name traitBody?
    ;

traitBody
    : '{'
      traitFlag*
      feature*
      '}'
    ;

traitFlag
    : 'package' '=' qualifiedName
    | 'hint' '=' STRING
    ;

traitRef
    : '@'? name
    ;

dataTransferObject
    : 'DataTransferObject' name ('extends' '@'? name)? dtoModifier* body=dtoBody?
    ;

dtoBody
    : '{'
      dtoFlag*
      feature*
      '}'
    ;

dtoFlag
    : 'package' '=' qualifiedName
    | 'validate' ('=' STRING)?
    | 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    ;

dtoModifier
    : 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | 'validate' '=' STRING
    ;

enumDecl
    : 'enum' name '{'
      enumOption*
      enumAttribute*
      (enumValue (',' enumValue)* ';'?)?
      '}'
    ;

enumOption
    : 'package' '=' qualifiedName
    | 'hint' '=' STRING
    | 'aggregateLifecycle'
    | 'ordinal'
    ;

enumAttribute
    : type name 'key'? ';'?
    ;

enumValue
    : name ('(' enumParameter (',' enumParameter)* ')')?
    ;

enumParameter
    : STRING
    | INT
    ;

basicType
    : 'BasicType' name ('with' traitRef (',' traitRef)*)* body=basicTypeBody?
    ;

basicTypeBody
    : '{'
      basicTypeFlag*
      feature*
      '}'
    ;

basicTypeFlag
    : 'belongsTo' ('@')? qualifiedName
    | 'package' '=' qualifiedName
    | 'validate' '=' STRING
    | 'gap'
    | 'nogap'
    | 'hint' '=' STRING
    | notPrefix? 'immutable'
    | notPrefix? 'cache'
    ;

// Tactical DDD Features - The core fix for attribute parsing
feature
    : association
    | repository
    | operation
    | attribute
    // Fallback to swallow unrecognized statements inside DDD blocks
    | rawStatement
    ;

association
    : ('--' | 'association') STRING? reference='@'? type name attributeOption* ';'?
    | ('--' | 'association') STRING? reference='@'? type ';'?
    ;

// Explicit attribute rule to avoid ambiguity
// Supports both Java-style (- Type name) and Kotlin-style (- name: Type)
attribute
    : STRING? visibility? reference=('-' | 'reference')? attrType=type attrName=name 'key'? attributeOption* attributeAssociationLabel? ';'?  #javaStyleAttribute
    | STRING? visibility? reference=('-' | 'reference')? attrName=name ':' attrType=type 'key'? attributeOption* attributeAssociationLabel? ';'?  #kotlinStyleAttribute
    ;

attributeAssociationLabel
    : ('--' | 'association') STRING
    ;

attributeOption
    : oppositeHolder
    | notPrefix? attributeOptionKey (('=' STRING)?)?
    ;

notPrefix
    : 'not' | '!'
    ;

attributeOptionKey
    : 'required'
    | 'notEmpty'
    | 'notBlank'
    | 'nullable'
    | 'unique'
    | 'index'
    | 'changeable'
    | 'persistent'
    | 'immutable'
    | 'transient'
    | 'cache'
    | 'inverse'
    | 'valid'
    | 'email'
    | 'future'
    | 'past'
    | 'pattern'
    | 'size'
    | 'min'
    | 'max'
    | 'decimalMax'
    | 'decimalMin'
    | 'digits'
    | 'length'
    | 'range'
    | 'scriptAssert'
    | 'url'
    | 'hint'
    | 'creditCardNumber'
    | 'assertTrue'
    | 'assertFalse'
    | 'cascade'
    | 'fetch'
    | 'databaseColumn'
    | 'databaseType'
    | 'databaseJoinTable'
    | 'databaseJoinColumn'
    | 'orderColumn'
    | 'validate'
    | 'orderby'
    ;

oppositeHolder
    : 'opposite' (('=' STRING) | name)
    | '<->' name
    ;

operation
    : operationWithParams
    | operationNoParams
    ;

// Service/Resource operations in Xtext allow omitting the `()` when there are no parameters.
// Keep this scoped to Service/Resource bodies to avoid ambiguity with Attributes in domain objects.
callableOperationNoParens
    : STRING? visibility? returnType=type name operationClause* ';'?
    | STRING? visibility? name operationClause* ';'?
    ;

operationWithParams
    : operationPrefix? returnType=type? name
      '(' parameterList? ')'
      operationClause*
      ';'?
    ;

operationNoParams
    : ('def' | '*') 'abstract'? visibility? returnType=type? name
      operationClause*
      ';'?
    ;

operationPrefix
    : ('def' | '*') 'abstract'? visibility?
    | visibility ('def' | '*')?
    ;

operationHint
    : ':' operationHintType stateTransition?
    ;

operationHintType
    : 'read-only' | 'read' | 'write'
    ;

operationClause
    : operationOption
    | operationHint
    | operationTail
    | throwsClause
    ;

throwsClause
    : 'throws' qualifiedNameList
    ;

operationOption
    : 'hint' '=' STRING
    | httpMethod
    | 'path' '=' STRING
    | 'return' '=' STRING
    ;

httpMethod
    : 'GET' | 'POST' | 'PUT' | 'DELETE'
    ;

operationTail
    : 'publish' eventTypeRef? 'to' operationTarget ('eventBus' '=' name)?
    | 'subscribe' eventTypeRef? 'to' operationTarget ('eventBus' '=' name)?
    | (('delegates' 'to') | '=>') '@'? qualifiedName
    ;

eventTypeRef
    : '@'? name
    ;

operationTarget
    : STRING
    | channelIdentifier
    | qualifiedName
    ;

// Fallback for complex operations that don't match standard signature
// This replaces RawFeature but is more constrained
// We'll rely on the specific operation rule first

contentBlock
    : '{' contentEntry* '}'
    ;

contentEntry
    : contentItem
    | feature
    ;

subdomainAttribute
    : 'type' '='? subdomainType
    | 'domainVisionStatement' '='? STRING
    ;

contentItem
    : contentBlock
    | aggregate
    | domainObject
    | service
    | resource
    | consumer
    | repository
    | boundedContextAttribute
    | aggregateAttribute
    | subdomainAttribute
    | moduleAttribute
    | setting
    | useCase
    | subdomain
    | module
    | application
    | contextMap
    | domain
    | ownerDecl
    ;

ownerDecl
    : 'owner' '='? name ';'?
    ;

aggregateAttribute
    : ('useCases' | 'userStories' | 'features' | 'userRequirements') '='? idList ';'?
    | ('likelihoodForChange' | 'structuralVolatility') '='? volatility ';'?
    | 'contentVolatility' '='? volatility ';'?
    | 'availabilityCriticality' '='? criticality ';'?
    | 'consistencyCriticality' '='? criticality ';'?
    | 'storageSimilarity' '='? similarity ';'?
    | 'securityCriticality' '='? criticality ';'?
    | 'securityZone' '='? STRING ';'?
    | 'securityAccessGroup' '='? STRING ';'?
    ;

volatility
    : 'UNDEFINED' | 'NORMAL' | 'RARELY' | 'OFTEN'
    ;

criticality
    : 'UNDEFINED' | 'NORMAL' | 'HIGH' | 'LOW'
    ;

similarity
    : 'UNDEFINED' | 'NORMAL' | 'HUGE' | 'TINY'
    ;

setting
    : 'basePackage' '=' qualifiedName ';'?
    ;

moduleAttribute
    : 'external'
    | 'hint' '=' STRING
    ;

// Supports both Java-style (Type name) and Kotlin-style (name: Type)
parameter
    : '@'? paramType=type paramName=name      #javaStyleParameter
    | '@'? paramName=name ':' paramType=type  #kotlinStyleParameter
    ;

parameterList
    : parameter (',' parameter)*
    ;

type
    : collectionType '<' innerType=type '>'
    | 'Map' '<' mapKeyType=type ',' mapValueType=type '>'
    | qualifiedName '<' innerType=type '>'
    | '@'? qualifiedName
    ;

collectionType
    : 'List' | 'Set' | 'Bag' | 'Collection'
    ;

service
    : 'Service' name (serviceModifier | dependency)* serviceBody?
    ;

serviceBody
    : '{' serviceBodyElement* '}'
    ;

serviceBodyElement
    : serviceModifier
    | dependency
    | association
    | operation
    | callableOperationNoParens
    | rawStatement
    ;

resource
    : 'Resource' name (resourceModifier | dependency)* resourceBody?
    ;

resourceBody
    : '{' resourceBodyElement* '}'
    ;

resourceBodyElement
    : resourceModifier
    | dependency
    | operation
    | callableOperationNoParens
    | rawStatement
    ;

consumer
    : 'Consumer' name (consumerModifier | dependency)* consumerBody?
    ;

consumerBody
    : '{' consumerBodyElement* '}'
    ;

consumerBodyElement
    : consumerModifier
    | dependency
    | rawStatement
    ;

repository
    : 'Repository' name (repositoryModifier | dependency)* repositoryBody?
    ;

repositoryBody
    : '{' repositoryBodyElement* '}'
    ;

repositoryBodyElement
    : repositoryModifier
    | dependency
    | repositoryMethod
    | rawStatement
    ;

repositoryMethod
    : visibility?
      (
          '@'? type name
          | name
      )
      ('(' parameterList? ')')?
      repositoryMethodOption*
      ';'?
    ;

serviceModifier
    : 'gap'
    | 'nogap'
    | 'webservice'
    | 'scaffold'
    | 'hint' '=' STRING
    | 'subscribe' 'to' (STRING | channelIdentifier) ('eventBus' '=' name)?
    ;

resourceModifier
    : 'gap'
    | 'nogap'
    | 'scaffold'
    | 'hint' '=' STRING
    | 'path' '=' STRING
    ;

consumerModifier
    : 'hint' '=' STRING
    | 'subscribe' 'to' (STRING | channelIdentifier) ('eventBus' '=' name)?
    | 'unmarshall' 'to' '@'? qualifiedName
    | ('queueName' | 'topicName') '=' channelIdentifier
    ;

dependency
    : ('>' | 'inject') '@'? qualifiedName
    ;

repositoryModifier
    : 'gap'
    | 'nogap'
    | 'hint' '=' STRING
    | 'subscribe' 'to' (STRING | channelIdentifier) ('eventBus' '=' name)?
    ;

repositoryMethodOption
    : 'throws' qualifiedNameList
    | 'hint' '=' STRING
    | 'cache'
    | 'gap'
    | 'nogap'
    | 'construct'
    | 'build'
    | 'map'
    | 'query' '=' STRING
    | 'condition' '=' STRING
    | 'select' '=' STRING
    | 'groupBy' '=' STRING
    | 'orderBy' '=' STRING
    | (('delegates' 'to') | '=>') '@'? qualifiedName
    | 'publish' eventTypeRef? 'to' operationTarget ('eventBus' '=' name)?
    | 'subscribe' eventTypeRef? 'to' operationTarget ('eventBus' '=' name)?
    ;

visibility
    : 'public' | 'private' | 'protected' | 'package'
    ;

// --- Application & choreography ---

application
    : 'Application' name? '{' applicationElement* '}'
    ;

applicationElement
    : commandDecl
    | flow
    | service
    | coordination
    | domainEvent
    | commandEvent
    ;

commandDecl
    : ('Command' | 'command') name ';'?
    ;

flow
    : ('Flow' | 'flow') name '{' flowStep* '}'
    ;

flowStep
    : flowCommandStep | flowEventStep | flowOperationStep
    ;

flowCommandStep
    : 'command' name flowInitiator? flowCommandTail? ';'?
    ;

flowCommandTail
    : flowDelegate? flowEmitsClause?
    ;

flowEventStep
    : 'event' flowEventTriggerList 'triggers' flowInvocationList ';'?
    ;

flowEventTriggerList
    : name (transitionOperator name)*  // event A + B triggers...
    ;

flowOperationStep
    : 'operation' name flowInitiator? flowOperationTail? ';'?
    ;

flowOperationTail
    : flowDelegate? flowEmitsClause?
    ;

flowInitiator
    : '[' 'initiated' 'by' STRING ']'
    ;

flowDelegate
    : 'delegates' 'to' name ('aggregate')? stateTransition?
    ;

flowInvocationList
    : flowInvocation (flowInvocationConnector)*
    ;

flowInvocationConnector
    : transitionOperator flowInvocation
    ;

flowInvocation
    : flowInvocationKind? name  // Kind is optional for subsequent invocations
    ;

flowInvocationKind
    : 'command' | 'operation'
    ;

flowEmitsClause
    : 'emits' 'event' flowEventList
    ;

flowEventList
    : name (transitionOperator name)*
    ;

coordination
    : ('Coordination' | 'coordination') name '{' coordinationStep* '}'
    ;

coordinationStep
    : coordinationPath ';'?
    ;

coordinationPath
    : name ('::' name)*
    ;

stateTransition
    : '['
      (idList)?
      ('->' targetState (transitionOperator targetState)*)?
      ']'
    ;

targetState
    : name ('*')?
    ;

transitionOperator
    : 'X' | 'x' | '+' | 'O' | 'o'
    ;

// --- Use Cases ---

useCase
    : 'UseCase' name ('{' (useCaseBody | useCaseFreeText)* '}')?
    ;

useCaseBody
    : useCaseActor
    | useCaseSecondaryActors
    | useCaseInteractionsBlock
    | useCaseBenefit
    | useCaseScope
    | useCaseLevel
    ;

useCaseActor
    : 'actor' '='? STRING
    ;

useCaseSecondaryActors
    : 'secondaryActors' '='? STRING (',' STRING)*
    ;

useCaseInteractionsBlock
    : 'interactions' '='? useCaseInteractionItem+
    ;

useCaseInteractionItem
    : urFeature ','?
    | useCaseReadOperation ','?  
    | STRING ','?
    | useCaseInteractionId ','?
    ;

useCaseInteractionId
    : name
    | READ
    | WITH
    | ITS
    ;

useCaseReadOperation
    : READ STRING WITH ITS STRING (',' STRING)*
    ;

urFeature
    : urStoryFeature
    | urNormalFeature
    ;

urStoryFeature
    : 'I' 'want' 'to' urVerb urEntityTail
    | 'I' 'want' 'to' STRING
    ;

urNormalFeature
    : urVerb urEntityTail
    ;

urVerb
    : READ
    | ID
    | 'create'
    | STRING
    ;

urEntityTail
    : urEntityArticle? STRING urEntityAttributes? urContainerEntity?
    ;

urEntityArticle
    : 'a' | 'an' | 'the'
    ;

urEntityAttributes
    : WITH (ITS | 'their') STRING (',' STRING)*
    ;

urContainerEntity
    : ('in' | 'for' | 'to') urEntityArticle? STRING
    ;

useCaseFreeText
    : (~'}')+
    ;

userStory
    : 'UserStory' name ('split' 'by' name)? '{' (userStoryXtextBody | userStoryBody | userStoryLine)* '}'
    ;

userStoryBody
    : 'As' ('a' | 'an')? STRING
      'I' 'want' 'to' (ID | 'do')? STRING
      'so' 'that' STRING
    ;

userStoryXtextBody
    : 'As' ('a' | 'an')? role=STRING
      urFeature+
      'so' 'that' benefit=STRING
      storyValuation?
    ;

storyValuation
    : 'and' 'that' promoted+=STRING (',' promoted+=STRING)* ('is' | 'are') 'promoted' ','?
      'accepting' 'that' harmed+=STRING (',' harmed+=STRING)* ('is' | 'are') ('reduced' | 'harmed')
    ;

userStoryLine
    : (~'}')+
    ;

name
    : ID
    | 'Map'
    | 'Service'
    | 'Event'
    | 'Command'
    | 'characteristic'
    | 'context'
    | 'in'
    | 'risk'
    | 'value'
    | 'AvailabilityCriticality'
    | 'ConsistencyCriticality'
    | 'ContentVolatility'
    | 'SecurityCriticality'
    | 'StorageSimilarity'
    | 'StructuralVolatility'
    | 'SecurityAccessGroup'
    | 'SeparatedSecurityZone'
    | 'SharedOwnerGroup'
    | 'PredefinedService'
    | 'Compatibilities'
    | 'X' | 'x' | 'O' | 'o' | 'U' | 'D' | 'S' | 'C' | 'P'
    | 'ACL' | 'CF' | 'OHS' | 'PL' | 'SK'
    | 'required' | 'notEmpty' | 'notBlank' | 'nullable' | 'unique' | 'index' | 'changeable'
    | 'persistent' | 'immutable' | 'transient' | 'cache' | 'inverse' | 'valid'
    | 'email' | 'future' | 'past' | 'pattern' | 'size' | 'min' | 'max' | 'digits'
    | 'decimalMax' | 'decimalMin' | 'length' | 'range' | 'scriptAssert' | 'url'
    | 'hint' | 'creditCardNumber' | 'assertTrue' | 'assertFalse'
    | 'cascade' | 'fetch' | 'databaseColumn' | 'databaseType'
    | 'databaseJoinTable' | 'databaseJoinColumn' | 'orderColumn'
    | 'validate' | 'orderby'
    | 'As' | 'a' | 'an' | 'I' | 'want' | 'to' | 'do' | 'so' | 'that'
    | READ | WITH | ITS
    | 'actor' | 'secondaryActors' | 'interactions' | 'benefit' | 'scope' | 'level'
    | 'split' | 'by' | 'and' | 'accepting' | 'promoted' | 'reduced' | 'harmed'
    | 'the' | 'their' | 'description'
    | 'relatedValue' | 'opposingValue' | 'isCore' | 'Stakeholder' | 'Stakeholders' | 'neutral'
    | 'protect' | 'create' | 'initiated'
    | 'useCases' | 'userStories' | 'features' | 'userRequirements'
    | 'likelihoodForChange' | 'structuralVolatility' | 'contentVolatility'
    | 'availabilityCriticality' | 'consistencyCriticality' | 'storageSimilarity' | 'securityCriticality'
    | 'securityZone' | 'securityAccessGroup'
    | 'external' | 'basePackage'
    | 'HIGH' | 'MEDIUM' | 'LOW' | 'NORMAL' | 'RARELY' | 'OFTEN' | 'HUGE' | 'TINY' | 'UNDEFINED'
    ;

useCaseBenefit
    : 'benefit' '='? STRING
    ;

useCaseScope
    : 'scope' '='? STRING
    ;

useCaseLevel
    : 'level' '='? STRING
    ;

// --- Stakeholders and Values ---

stakeholderSection
    : 'Stakeholders' ('of' idList)? '{' stakeholderItem* '}'
    ;

stakeholderItem
    : stakeholderGroup | stakeholder
    ;

stakeholderGroup
    : 'StakeholderGroup' name ('{' stakeholder* '}')?
    ;

stakeholder
    : 'Stakeholder' name ('{' stakeholderAttribute* '}')?
    ;

stakeholderAttribute
    : 'influence' '='? name
    | 'interest' '='? name
    | 'priority' '='? name
    | 'impact' '='? name
    | 'description' '='? STRING
    | consequences
    | consequenceItem
    ;

consequences
    : 'consequences' consequenceItem*
    ;

consequenceItem
    : ('good' | 'bad' | 'action') STRING name?
    ;

valueRegister
    : 'ValueRegister' name ('for' name)? '{'
      (valueCluster | value | valueEpic | valueNarrative | valueWeigthing)*
      '}'
    ;

valueCluster
    : 'ValueCluster' name '{' (valueClusterAttribute | value | valueElicitation)* '}'
    ;

valueClusterAttribute
    : 'core' '='? (name | STRING)
    | 'demonstrator' '='? STRING
    | 'relatedValue' '='? STRING
    | 'opposingValue' '='? STRING
    ;

value
    : 'Value' name '{' (valueAttribute | valueElicitation)* '}'
    ;

valueAttribute
    : 'core' '='? (name | STRING)
    | 'isCore'
    | 'demonstrator' '='? STRING
    | 'relatedValue' '='? STRING
    | 'opposingValue' '='? STRING
    ;

valueElicitation
    : ('Stakeholder' | 'Stakeholders') name ('{' valueElicitationOption* '}')?
    ;

valueElicitationOption
    : 'priority' '='? name
    | 'impact' '='? name
    | 'consequences' valueConsequenceEntry+
    ;

valueConsequenceEntry
    : valueConsequence
    | valueAction
    ;

valueConsequence
    : ('good' | 'bad' | 'neutral') STRING
    ;

valueAction
    : 'action' STRING (name | STRING)?
    ;

valueEpicClause
    : 'realization' 'of' STRING
    | 'reduction' 'of' STRING
    ;

valueEpic
    : 'ValueEpic' name '{'
      'As' ('a' | 'an')? name
      'I' 'value' STRING 'as' 'demonstrated' 'in'
      valueEpicClause+
      '}'
    ;

valueNarrative
    : 'ValueNarrative' name '{'
      'When' 'the' 'SOI' 'executes' STRING ','
      'stakeholders' 'expect' 'it' 'to'
        (
          'promote'
          | 'promote,' 'protect' 'or' 'create'
          | 'promote' ',' 'protect' 'or' 'create'
        )
      STRING ','?
      'possibly' 'degrading' 'or' 'prohibiting' STRING
      'with' 'the' 'following' 'externally' 'observable' 'and/or' 'internally' 'auditable' 'behavior:' STRING
      '}'
    ;

valueWeigthing
    : 'ValueWeigthing' name '{'
      'In' 'the' 'context' 'of' 'the' 'SOI,'
      'stakeholder' name
      'values' STRING 'more' 'than' STRING
      'expecting' 'benefits' 'such' 'as' STRING
      'running' 'the' 'risk' 'of' 'harms' 'such' 'as' STRING
      '}'
    ;

rawStatement
    : ~(';' | '{' | '}'
        | 'Aggregate'
        | 'BoundedContext'
        | 'ContextMap'
        | 'Domain'
        | 'Subdomain'
        | 'UseCase'
        | 'UserStory'
        | 'Stakeholders'
        | 'ValueRegister'
        | 'Application'
        | 'Flow'
        | 'Coordination'
        | 'Module'
        | 'Service'
        | 'Repository'
        | 'Resource'
        | 'Consumer'
        | 'Entity'
        | 'ValueObject'
        | 'DomainEvent'
        | 'Event'
        | 'CommandEvent'
        | 'Command'
        | 'DataTransferObject'
        | 'Trait'
        | 'BasicType'
        | 'enum'
      )
      (~(';' | '{' | '}'
        | 'Aggregate'
        | 'BoundedContext'
        | 'ContextMap'
        | 'Domain'
        | 'Subdomain'
        | 'UseCase'
        | 'UserStory'
        | 'Stakeholders'
        | 'ValueRegister'
        | 'Application'
        | 'Flow'
        | 'Coordination'
        | 'Module'
        | 'Service'
        | 'Repository'
        | 'Resource'
        | 'Consumer'
        | 'Entity'
        | 'ValueObject'
        | 'DomainEvent'
        | 'Event'
        | 'CommandEvent'
        | 'Command'
        | 'DataTransferObject'
        | 'Trait'
        | 'BasicType'
        | 'enum'
      ))* ';'?
    ;

// --- ServiceCutter Configuration DSL (minimal support) ---

serviceCutterElement
    : scAggregate
    | scEntity
    | scSecurityAccessGroup
    | scSeparatedSecurityZone
    | scSharedOwnerGroup
    | scPredefinedService
    | scCompatibilities
    | scUseCase
    | scCharacteristic
    ;

scAggregate
    : 'Aggregate' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scEntity
    : 'Entity' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scSecurityAccessGroup
    : 'SecurityAccessGroup' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scSeparatedSecurityZone
    : 'SeparatedSecurityZone' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scSharedOwnerGroup
    : 'SharedOwnerGroup' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scPredefinedService
    : 'PredefinedService' STRING '{' (STRING (',' STRING)*)? '}' ';'?
    ;

scCompatibilities
    : 'Compatibilities' '{' (scCharacteristic)* '}'
    ;

scUseCase
    : 'UseCase' name '{' scUseCaseElement* '}'
    ;

scUseCaseElement
    : scIsLatencyCritical
    | scReads
    | scWrites
    ;

scIsLatencyCritical
    : 'isLatencyCritical' '=' 'true'
    ;

scReads
    : 'reads' scUseCaseNanoentities?
    ;

scWrites
    : 'writes' scUseCaseNanoentities?
    ;

// Mirrors Xtext behavior: allows whitespace and comma-separated lists.
scUseCaseNanoentities
    : STRING (','? STRING)*
    ;

scCharacteristic
    : scAvailabilityCriticality
    | scConsistencyCriticality
    | scContentVolatility
    | scSecurityCriticality
    | scStorageSimilarity
    | scStructuralVolatility
    ;

scAvailabilityCriticality
    : 'AvailabilityCriticality' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scConsistencyCriticality
    : 'ConsistencyCriticality' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scContentVolatility
    : 'ContentVolatility' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scSecurityCriticality
    : 'SecurityCriticality' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scStorageSimilarity
    : 'StorageSimilarity' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scStructuralVolatility
    : 'StructuralVolatility' '{' 'characteristic' name (scNanoentities)? '}'
    ;

scNanoentities
    : STRING (',' STRING)*
    ;

// --- Helpers ---

idList
    : name (',' name)*
    ;

qualifiedNameList
    : qualifiedName (',' qualifiedName)*
    ;

qualifiedName
    : name ('.' name)*
    ;

channelIdentifier
    : name (('.' | '/' | ':') name)*
    ;

// --- Lexer Rules ---

// Keywords for UseCase interactions (must come before ID)
READ : 'read';
WITH : 'with';
ITS : 'its';

INT : [0-9]+;

ID
    : '^'? [a-zA-Z_] [a-zA-Z0-9_]*
    ;

STRING
    : '"' ( '\\' . | ~[\\"] )* '"'
    | '\'' ( '\\' . | ~[\\'] )* '\''
    ;

// Comments
COMMENT
    : '//' ~[\r\n]* -> channel(HIDDEN)
    ;

BLOCK_COMMENT
    : '/*' .*? '*/' -> channel(HIDDEN)
    ;

WS
    : [ \t\r\n]+ -> skip
    ;
