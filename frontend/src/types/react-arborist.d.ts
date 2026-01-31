// src/types/react-arborist.d.ts
declare module 'react-arborist' {
  import { ComponentType } from 'react';
  export const Tree: ComponentType<any>;
  export type TreeProps = any;
  // Ajoute d'autres exports si besoin, mais ça suffit pour Tree
}