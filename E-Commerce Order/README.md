# E-Commerce Order MCP Server

## AI Development - Cycle 2

This project is developed as part of the AI Development Preparation assignment.

## Cycle Information

- Cycle: 2
- Topic: MCP Server
- Use Case: E-Commerce Order MCP Server
- Duration: Day 16 - Day 30
- Deadline: 27 August 2026
- Status: Compulsory

## Problem Statement

The purpose of this project is to build an MCP server for an E-Commerce order system.

The server will provide tools that allow an MCP client to work with mock E-Commerce data.

The selected use case provides three main operations:

- Track an order
- Check product stock
- Initiate a return

The project will use a local mock product and order database.

## Selected Use Case

### UC4 - E-Commerce Order MCP Server

The selected use case is the E-Commerce Order MCP Server from the given AI Development assignment.

The server will expose the following tools:

1. `track_order`
2. `check_stock`
3. `initiate_return`

The data will be stored locally using JSON.

## Planned Architecture

```text
MCP Client
    |
    | MCP
    v
E-Commerce MCP Server
    |
    +---- track_order
    |
    +---- check_stock
    |
    +---- initiate_return
    |
    v
Mock E-Commerce Data
(JSON)