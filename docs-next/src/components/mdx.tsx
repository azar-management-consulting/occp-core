import defaultMdxComponents from 'fumadocs-ui/mdx';
import type { MDXComponents } from 'mdx/types';

// Re-export the richer widgets so every MDX page can use them without
// a local import. Kept in sync with fumadocs-ui 16.8.
import {
  Callout,
  CalloutContainer,
  CalloutTitle,
  CalloutDescription,
} from 'fumadocs-ui/components/callout';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import { Accordion, Accordions } from 'fumadocs-ui/components/accordion';
import { Card, Cards } from 'fumadocs-ui/components/card';
import { Steps, Step } from 'fumadocs-ui/components/steps';
import { File, Files, Folder } from 'fumadocs-ui/components/files';
import { TypeTable } from 'fumadocs-ui/components/type-table';

/**
 * MDX components registered for every page.
 *
 * Defaults pulled from `fumadocs-ui/mdx`:
 *  - `pre` / `CodeBlockTabs*` (code blocks with built-in copy + language bar)
 *  - `Callout*` (brand styling via `--color-fd-primary`)
 *  - `Card` / `Cards`
 *
 * Additions (explicit re-exports for authoring ergonomics):
 *  - <Tabs> / <Tab>          — multi-language code switching
 *  - <Accordions> / <Accordion> — FAQ / collapsible reference
 *  - <Steps> / <Step>        — ordered walkthroughs
 *  - <Files> / <Folder> / <File> — file-tree illustrations
 *  - <TypeTable>             — typed prop tables for SDK reference
 */
export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    // Callouts (already in default but re-exported explicitly so it
    // survives any future upstream default-bundle changes).
    Callout,
    CalloutContainer,
    CalloutTitle,
    CalloutDescription,
    // Multi-language / multi-tab content
    Tabs,
    Tab,
    // FAQ-style content
    Accordions,
    Accordion,
    // Walkthrough / quickstart ergonomics
    Steps,
    Step,
    // Reference / prop tables
    Card,
    Cards,
    File,
    Files,
    Folder,
    TypeTable,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;

declare global {
  type MDXProvidedComponents = ReturnType<typeof getMDXComponents>;
}
