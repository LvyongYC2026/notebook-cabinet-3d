const variants = new Set(['glass', 'metal']);

export function frontVariantOf(object) {
  for (let node = object; node; node = node.parent) {
    if (variants.has(node.userData?.drawer_front_variant)) return node.userData.drawer_front_variant;
  }
  return null;
}

// Each dedicated assembly stays under its existing Tray. Switching visibility
// never changes the mechanism, occupancy, USB connections or flexible cables.
export class DrawerFrontVariants {
  constructor(root) {
    this.roots = new Map([...variants].map(id => [id, []]));
    root.traverse(node => {
      const id = node.userData?.drawer_front_variant;
      if (variants.has(id) && !frontVariantOf(node.parent)) this.roots.get(id).push(node);
    });
    this.supported = [...this.roots.values()].every(nodes => nodes.length > 0);
    this.current = null;
    if (!this.supported) return;
    // GLTF extras initial_hidden describe the exported default. setupModel may
    // apply that flag to leaves; normalize ONLY these dedicated assemblies so
    // revealing their parent later also reveals the chosen front and handle.
    for (const nodes of this.roots.values()) for (const root of nodes) {
      root.traverse(node => { node.visible = true; });
    }
  }

  set(id) {
    if (!this.supported || !variants.has(id)) return false;
    for (const [variant, nodes] of this.roots) for (const node of nodes) node.visible = variant === id;
    this.current = id;
    return true;
  }
}
