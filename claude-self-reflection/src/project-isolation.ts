import { createHash } from 'crypto';
import { QdrantClient } from '@qdrant/js-client-rest';

export interface ProjectIsolationConfig {
  mode: 'isolated' | 'shared' | 'hybrid';
  allowCrossProject: boolean;
  projectIdentifier?: string;
}

export class ProjectIsolationManager {
  private client: QdrantClient;
  private config: ProjectIsolationConfig;

  constructor(client: QdrantClient, config: ProjectIsolationConfig) {
    this.client = client;
    this.config = config;
  }

  /**
   * Get collection name based on isolation mode
   */
  getCollectionName(projectName?: string): string {
    if (this.config.mode === 'isolated' && projectName) {
      // Create project-specific collection name
      const projectHash = createHash('md5')
        .update(projectName)
        .digest('hex')
        .substring(0, 8);
      return `conv_${projectHash}`;
    }
    
    // Default to shared collection
    return 'conversations';
  }

  /**
   * Get project filter for queries
   */
  getProjectFilter(projectName?: string): any {
    if (!projectName || this.config.mode === 'shared') {
      return {};
    }

    return {
      filter: {
        must: [{
          key: 'project_id',
          match: { value: projectName }
        }]
      }
    };
  }

  /**
   * Detect current project from environment
   */
  static detectCurrentProject(): string | undefined {
    // Check environment variables
    const fromEnv = process.env.CLAUDE_PROJECT_NAME;
    if (fromEnv) return fromEnv;

    // Try to detect from working directory
    const cwd = process.cwd();
    const projectMatch = cwd.match(/\/([^\/]+)$/);
    return projectMatch ? projectMatch[1] : undefined;
  }

  /**
   * Ensure collection exists for project
   */
  async ensureProjectCollection(projectName: string, vectorSize: number): Promise<void> {
    const collectionName = this.getCollectionName(projectName);
    
    try {
      await this.client.getCollection(collectionName);
    } catch (error) {
      // Collection doesn't exist, create it
      await this.client.createCollection(collectionName, {
        vectors: {
          size: vectorSize,
          distance: 'Cosine'
        }
      });
      console.error(`Created project-specific collection: ${collectionName}`);
    }
  }
}

export const DEFAULT_ISOLATION_CONFIG: ProjectIsolationConfig = {
  mode: 'hybrid',
  allowCrossProject: false,
  projectIdentifier: ProjectIsolationManager.detectCurrentProject()
};