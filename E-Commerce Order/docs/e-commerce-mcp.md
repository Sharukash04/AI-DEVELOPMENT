# E-Commerce Order MCP Server - Day 1 Notes

## 1. Cycle 2

Cycle 2 of the AI Development Preparation assignment is about building an MCP Server.

The cycle is a 15-day cycle and is compulsory.

## 2. What is MCP?

MCP stands for Model Context Protocol.

In this project, MCP is used to provide a standard way for an MCP client to communicate with our E-Commerce server and use the tools provided by the server.

The MCP server will provide tools that can perform operations on mock E-Commerce data.

## 3. Selected Use Case

The selected use case for Cycle 2 is:

**E-Commerce Order MCP Server**

This is UC4 from the use-case list provided in the assignment.

The server will work with a mock product and order database.

## 4. Required Tools

The selected use case requires three tools.

### 4.1 track_order

This tool will be used to track the status of an E-Commerce order.

Example purpose:

```text
Order ID
    |
    v
track_order
    |
    v
Order information